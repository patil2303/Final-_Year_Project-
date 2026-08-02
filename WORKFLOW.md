# 🔄 End-to-End Project Workflow & Architecture

This document provides a comprehensive breakdown of **what happens inside this project**, **how each component works**, and **how data flows** from an uploaded photo or PDF into a formatted Excel (`.xlsx`) spreadsheet or CSV file using our **100% On-Device Local Machine Learning Pipeline**.

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
       │ 2. OpenCV Grayscale Preprocessing │
       │    • Grayscale Conversion         │
       │    • CLAHE Shadow Elimination     │
       │    • Auto-Deskew & Denoising      │
       └───────────────────────────────────┘
                        │
                        ▼
       ┌───────────────────────────────────┐
       │ 3. OpenCV Morphological Grid      │
       │    • Horizontal & Vertical Kernels│
       │    • Intersection Point Detection │
       │    • Cell Matrix Bounding Boxes   │
       └───────────────────────────────────┘
                        │
                        ▼
       ┌───────────────────────────────────┐
       │ 4. Custom PyTorch 3-Block CNN     │
       │    • Local Digit Classification   │
       │    • 99.55% Accuracy on MNIST     │
       │    • TTA Majority Voting          │
       └───────────────────────────────────┘
                        │
                        ▼
       ┌───────────────────────────────────┐
       │ 5. Major Project Domain Services │
       │    • Student Metadata Extraction  │
       │    • Levenshtein Branch Matcher   │
       │    • Ink Density Sum Verifier     │
       └───────────────────────────────────┘
                        │
                        ▼
       ┌───────────────────────────────────┐
       │ 6. Interactive Web UI & Exporters │
       │    • Student Metadata Banner      │
       │    • Editable Spreadsheet Grid    │
       │    • OpenPyXL Excel & CSV Download│
       └───────────────────────────────────┘
```

---

## 🔬 Detailed Phase Breakdown

### Phase 1: Universal File Ingestion (`backend/utils.py`)
- Accepts any format (PNG, JPG, JPEG, WEBP, TIFF, BMP, PDF).
- Multi-page PDFs are converted to high-DPI RGB images using PyMuPDF (`fitz`).

### Phase 2: OpenCV Preprocessing & Grayscale Normalization (`backend/utils.py`)
- **Grayscale Conversion**:
  $$I_{\text{gray}} = 0.299R + 0.587G + 0.114B$$
- **CLAHE (Contrast Limited Adaptive Histogram Equalization)**:
  Amplifies contrast in localized $8 \times 8$ grid blocks to restore faded ink and eliminate uneven paper lighting/shadows.
- **Auto-Deskew & Denoising**:
  Detects document rotation angle using Minimum Area Rectangles and applies bilateral filtering to smooth background noise while keeping edges crisp.

### Phase 3: Morphological Grid & Line Extraction (`backend/section_detector.py`)
- Isolates table grid lines using OpenCV horizontal ($K_h$) and vertical ($K_v$) structuring elements.
- Extracts junction coordinate points $(x, y, w, h)$ for every individual cell crop.

### Phase 4: Custom PyTorch CNN Classification (`backend/mnist_classifier.py` & `backend/ocr_engine.py`)
- Single digit cell crops are passed through our custom **3-Block Convolutional Neural Network** (`backend/models/mnist_cnn.pt`).
- Features:
  - 3 Conv-BatchNorm-ReLU-MaxPool-Dropout blocks.
  - Fully-connected dense layer with Dropout (0.5).
  - Test-Time Augmentation (TTA) 5-crop majority voting for low-confidence samples.

### Phase 5: Domain Metadata & Verification Services (`backend/services/`)
- **Student Metadata**: Extracts PRN, Student Name, Branch (using Levenshtein string distance matching), Division, and Semester.
- **Marks Verification**: Analyzes dark ink pixel density after margin shaving and validates that question scores sum up to the total score.

### Phase 6: Interactive Web UI & Export (`static/js/app.js` & `backend/data_formatter.py`)
- Extracted data is presented in an in-browser spreadsheet editor with a **Student & Document Metadata Banner**.
- Export options:
  - **Excel (`.xlsx`)**: Formatted headers, alternating row colors, auto-adjusted column widths.
  - **CSV (`.csv`)**: Formula injection sanitization (`=`, `+`, `-`, `@` stripping).
