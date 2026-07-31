# 🔄 End-to-End Project Workflow & Architecture

This document provides a comprehensive breakdown of **what happens inside this project**, **how each component works**, and **how data flows** from an uploaded photo or PDF into a formatted Excel (`.xlsx`) spreadsheet or CSV file.

---

## 🗺️ High-Level System Workflow Diagram

```text
[ User Uploads File (PNG, JPG, PDF, WEBP, etc.) ]
                        │
                        ▼
       ┌───────────────────────────────────┐
       │ 1. Universal Image Ingestion     │
       │    • Converts PDF → Images        │
       │    • Handles EXIF rotation        │
       └───────────────────────────────────┘
                        │
                        ▼
       ┌───────────────────────────────────┐
       │ 2. Preprocessing & Enhancement   │
       │    • CLAHE Shadow Elimination     │
       │    • Auto-Deskew & Bilateral Filter│
       └───────────────────────────────────┘
                        │
                        ▼
       ┌───────────────────────────────────┐
       │ 3. Grid Geometry & Box Detection  │
       │    • Contour Analysis             │
       │    • Cell Bounding Box Matrix     │
       └───────────────────────────────────┘
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
    [ Grid Mode ]               [ Freeform Mode ]
    (Cell Crops)                (Full Image OCR)
         │                             │
         ▼                             ▼
 ┌───────────────────────────┐   ┌───────────────────────────┐
 │ 4. Two-Tier Recognizer    │   │ 4. EasyOCR Fallback Engine│
 │  • Tier 1: MNIST CNN      │   │  • Multi-pass contrast    │
 │    (Conf >= 0.70 -> Accept│   │  • Allowlist '0-9.-'      │
 │  • Tier 2: EasyOCR        │   └───────────────────────────┘
 └───────────────────────────┘                 │
               │                               │
               └──────────────┬────────────────┘
                              ▼
       ┌───────────────────────────────────┐
       │ 5. Section & Matrix Detector      │
       │    • Align Row/Col Centroids      │
       │    • Normalize & Repair Misreads  │
       └───────────────────────────────────┘
                        │
                        ▼
       ┌───────────────────────────────────┐
       │ 6. Interactive Spreadsheet UI     │
       │    • Edit cells & headers         │
       │    • Add/Remove rows & columns    │
       └───────────────────────────────────┘
                        │
                        ▼
       ┌───────────────────────────────────┐
       │ 7. Data Formatter & Exporter      │
       │    • Excel (.xlsx) Styling        │
       │    • CSV Injection Protection     │
       └───────────────────────────────────┘
```

---

## 🔬 Detailed Step-by-Step Component Breakdown

### 1. Ingestion & Multi-Format Parsing (`backend/utils.py`)
- **Function**: `universal_file_to_cv2_images(file_bytes, filename)`
- **How it works**:
  - Checks if the uploaded file is a PDF (via magic bytes `%PDF` or `.pdf` extension).
  - Uses `pypdfium2` to render each PDF page at 300 DPI (`scale=2.0`) for high-contrast OCR.
  - If the file is an image (PNG, JPEG, WEBP, TIFF, BMP, GIF), it uses `Pillow` with `ImageOps.exif_transpose` to handle smartphone camera orientations automatically.

---

### 2. Preprocessing & Contrast Enhancement (`backend/utils.py`)
- **Functions**: `preprocess_handwritten_image()`, `deskew_image()`, `preprocess_image()`
- **How it works**:
  - **Shadow Elimination**: Applies **CLAHE** (Contrast Limited Adaptive Histogram Equalization) to balance uneven lighting across paper photos.
  - **Denoising**: Uses bilateral filtering (`d=7, sigmaColor=50`) to remove paper texture grain without blurring stroke edges.
  - **Auto-Deskew**: Calculates min-area bounding rectangle of ink points to detect document rotation angles (-45° to +45°) and rotates back to 0°.

---

### 3. Grid Geometry Detection (`backend/ocr_engine.py`)
- **Function**: `detect_grid_cell_boxes(img)`
- **How it works**:
  - Converts image to binary inverse threshold to isolate cell lines.
  - Runs `cv2.findContours()` with `RETR_TREE` hierarchy.
  - Filters contour bounding boxes by aspect ratio, minimum area (> 350 px), and removes duplicate nested sub-contours.
  - Groups cells into rows by Y-center distance (`bh * 0.55`) and sorts each row left-to-right to build a 2D geometry matrix: `[[cell_0_0, cell_0_1, ...], [cell_1_0, ...]]`.

---

### 4. Two-Tier OCR & MNIST CNN Recognizer (`backend/mnist_classifier.py` & `backend/ocr_engine.py`)
- **Functions**: `classify_digit()`, `_ocr_single_cell_crop()`
- **How it works**:

```text
               Input Cell Crop (BGR Image)
                           │
                           ▼
              [ Check std deviation > 6.0 ]
              (Empty cell guard -> return "")
                           │
                           ▼
          ┌─────────────────────────────────┐
          │ Preprocessing for MNIST Format  │
          │ 1. Convert to Grayscale & Invert│
          │ 2. OTSU binarize foreground ink │
          │ 3. Crop tight bounding box      │
          │ 4. Pad to square & resize 28x28 │
          │ 5. Normalize float [0, 1]       │
          └─────────────────────────────────┘
                           │
                           ▼
              [ MNIST 3-Block CNN Model ]
                           │
         ┌─────────────────┴─────────────────┐
         ▼                                   ▼
[ Softmax Confidence >= 0.70 ]   [ Softmax Confidence < 0.70 ]
         │                                   │
         ▼                                   ▼
(Accept CNN Digit Prediction)    (Fallback to EasyOCR + CLAHE)
```

- **CNN Model Architecture (`MNISTNet`)**:
  - **Block 1**: `Conv2d(1→32)` → `BatchNorm` → `ReLU` → `Conv2d(32→32)` → `BatchNorm` → `ReLU` → `MaxPool(2x2)` → `Dropout(0.25)`
  - **Block 2**: `Conv2d(32→64)` → `BatchNorm` → `ReLU` → `Conv2d(64→64)` → `BatchNorm` → `ReLU` → `MaxPool(2x2)` → `Dropout(0.25)`
  - **Block 3**: `Conv2d(64→128)` → `BatchNorm` → `ReLU` → `AdaptiveAvgPool2d(1x1)`
  - **Head**: `Flatten` → `Dropout(0.5)` → `Linear(128 → 10)`
  - **Accuracy**: **99.55%** on 10,000 test samples.

---

### 5. Section & Matrix Assembly (`backend/section_detector.py`)
- **Function**: `detect_sections_and_tables(ocr_items, img_shape)`
- **How it works**:
  - **Grid Mode**: If tokens contain explicit `grid_row` and `grid_col` coordinates, directly populates the output matrix `grid_matrix[row][col]` with 100% positional accuracy.
  - **Freeform Mode**: Groups tokens by Y-center distance (`avg_height * 0.65`) into rows, clusters X-centers into column centroids, and maps each token to its nearest column.

---

### 6. Text Repair & Normalization (`backend/ocr_engine.py`)
- **Function**: `clean_and_normalize_ocr_text(raw_text)`
- **How it works**:
  - Removes non-numeric noise symbols (currency symbols, trailing brackets).
  - Repairs common OCR character confusion:
    - `'O'`, `'o'`, `'D'`, `'Q'` ➔ `'0'`
    - `'I'`, `'l'`, `'|'`, `'/'`, `'!'` ➔ `'1'`
    - `'Z'`, `'z'` ➔ `'2'`
    - `'S'`, `'s'` ➔ `'5'`
    - `'G'`, `'b'` ➔ `'6'`
    - `'B'` ➔ `'8'`
    - `'q'`, `'g'`, `'P'` ➔ `'9'`
  - Converts valid numeric strings to native `int` or `float` types.

---

### 7. Interactive Frontend Editor (`static/js/spreadsheet_editor.js`)
- **How it works**:
  - Receives JSON section structures from `/api/extract`.
  - Renders an interactive spreadsheet UI with section tab switching.
  - Allows real-time inline editing of headers and cell values.
  - Supports dynamic row/column insertion (`addRow()`, `addColumn()`).
  - Keeps numeric types (`cell.value`, `cell.is_number`) synchronized with display text.

---

### 8. Excel & CSV Export Engine (`backend/data_formatter.py`)
- **Functions**: `export_to_excel_bytes()`, `export_to_csv_string()`, `_sanitize_csv_value()`
- **How it works**:
  - **Excel Exporter (`openpyxl`)**:
    - Creates a master **Summary sheet** with styled dark headers (`#1E293B`) and section banners (`#475569`).
    - Formats numeric cells with `#,#0.00` (floats) or `#,#0` (integers).
    - Creates individual tab sheets for multi-section documents.
    - Automatically calculates optimal column widths based on content length.
  - **CSV Exporter**:
    - Includes section separator headers (`# --- SECTION: Title ---`).
    - **CSV Injection Defense**: Checks if any cell text begins with formula triggers (`=`, `+`, `-`, `@`, `\t`) and escapes them with a single quote `'` to prevent malicious command execution when opened in Microsoft Excel.

---

## 💻 Summary Table of Module Roles

| Module | Primary Responsibility | Key Output |
| :--- | :--- | :--- |
| `backend/app.py` | FastAPI REST endpoints & HTTP routing | JSON Responses, File Downloads |
| `backend/mnist_classifier.py` | PyTorch CNN digit model training & inference | `(digit_str, confidence_float)` |
| `backend/ocr_engine.py` | Two-tier OCR pipeline & cell box detection | List of OCR Token objects |
| `backend/section_detector.py` | Table matrix assembly & column clustering | Section Data Dicts |
| `backend/data_formatter.py` | Excel workbook & CSV string generation | Binary `.xlsx` bytes / `.csv` text |
| `backend/utils.py` | File decoding, PDF rendering, image enhancement | OpenCV BGR images |
| `static/js/app.js` | Web UI upload, drag-and-drop & API fetch | Interactive UX |
| `static/js/spreadsheet_editor.js` | Editable spreadsheet DOM renderer | Updated Sections Model |
