# ⚡ Local Machine Learning & Hybrid Architecture Documentation

---

## 🏛️ System Architecture Overview

This project implements an **On-Device Local Machine Learning Core** with an optional cloud extension. It combines **OpenCV Image Processing**, **Custom Local PyTorch 3-Block CNN** (for digit recognition), and **Domain Extraction Services** (for student metadata and mark sum verification).

```text
[ Input Document (Photo / Scanned PDF) ]
                   │
                   ▼
┌──────────────────────────────────────────────────┐
│  STEP 1: OpenCV Preprocessing & Grayscale        │
│  - Grayscale conversion & CLAHE enhancement      │
│  - Adaptive thresholding & noise reduction       │
└──────────────────┬───────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────┐
│  STEP 2: OpenCV Morphological Grid Detector      │
│  - Horizontal & vertical line kernel extraction  │
│  - Table boundary & cell matrix segmentation     │
│  - Junction coordinate extraction                │
└──────────────────┬───────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────┐
│  STEP 3: Custom PyTorch 3-Block CNN (Local Model)│
│  - Evaluates individual digit & numeric crops    │
│  - Trained on 70,000 MNIST dataset samples       │
│  - 99.55% Test Accuracy & TTA Majority Voting    │
└──────────────────┬───────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────┐
│  STEP 4: Student Metadata & Sum Verification     │
│  - Levenshtein Branch Normalization (IT/CSE/AIDS)│
│  - PRN digit validation & whitelisting           │
│  - Cell dark ink density analysis & sum check    │
└──────────────────┬───────────────────────────────┘
                   │
                   ▼
[ Formatted Interactive Excel Sheet & CSV Workbook ]
```

---

## 🔬 Detailed Step-by-Step Breakdown

### 1. STEP 1: OpenCV Image Preprocessing & Grayscale Normalization
- **Grayscale Conversion**:
  $$I_{\text{gray}} = 0.299R + 0.587G + 0.114B$$
  Eliminates color noise, shadows, and background color tinting.
- **CLAHE (Contrast Limited Adaptive Histogram Equalization)**:
  Enhances local contrast across small $(8 \times 8)$ image tiles, making faint pencil marks or faded ink clearly visible.
- **Bilateral Filtering & Deskewing**:
  Removes high-frequency noise while preserving sharp digit boundaries and corrects camera rotational tilt.

### 2. STEP 2: Structural Grid Detection (OpenCV Morphological Engine)
- **Horizontal Kernel**: $K_h = \text{getStructuringElement}(\text{MORPH\_RECT}, (\text{width}/25, 1))$
- **Vertical Kernel**: $K_v = \text{getStructuringElement}(\text{MORPH\_RECT}, (1, \text{height}/25))$
- Identifies table bounding boxes and cell coordinate junctions $(x, y, w, h)$ without needing external API keys.

### 3. STEP 3: Digit Recognition via Custom PyTorch CNN Model
- For all single-digit and numeric cell crops within the detected grid, the system runs local deep learning inference using our pre-trained PyTorch model (`backend/models/mnist_cnn.pt`).
- **PyTorch Model Architecture**:
  - **Conv Block 1**: `Conv2d(1, 32, k=3, p=1) -> BatchNorm2d -> ReLU -> Conv2d(32, 32, 3) -> BatchNorm2d -> ReLU -> MaxPool2d(2, 2) -> Dropout(0.25)`
  - **Conv Block 2**: `Conv2d(32, 64, k=3, p=1) -> BatchNorm2d -> ReLU -> Conv2d(64, 64, 3) -> BatchNorm2d -> ReLU -> MaxPool2d(2, 2) -> Dropout(0.25)`
  - **Dense Layer**: `Linear(64 * 5 * 5, 256) -> BatchNorm1d -> ReLU -> Dropout(0.5) -> Linear(256, 10)`
- **Test-Time Augmentation (TTA)**:
  If initial CNN confidence is below $0.55$, the engine generates 5 augmented crops (rotated, shifted, scaled) and performs majority voting for maximum classification robustness.

### 4. STEP 4: Student Metadata & Mark Sum Verification
- **Header Metadata Extraction (`backend/services/header_extraction_service.py`)**:
  - PRN validation: Strips noise characters, extracting exact digit sequences.
  - Levenshtein Distance string matching for branch names (`IT`, `CSE`, `AIDS`, `AIML`, `EXTC`, `CIVIL`, `MECHANICAL`).
  - Division & Semester normalization (`I` → `1`, `II` → `2`).
- **Mark Verification (`backend/services/marks_table_extraction_service.py`)**:
  - Ink Density Thresholding: Evaluates dark pixel density after 15% margin shaving to separate empty cells from handwritten scores.
  - Mathematical Sum Check: Validates that individual question scores ($m_{1a} + m_{1b} + \dots$) sum up to the total score.

---

## 🎯 Why This Local ML Architecture Is Ideal for Academic Submission

1. **100% On-Device Code Execution**:
   - Zero API key dependencies or third-party cloud subscription requirements.
2. **Demonstrates Real Computer Science & Engineering Work**:
   - Custom PyTorch CNN digit classification trained on 70,000 images.
   - OpenCV morphological line kernel signal processing.
   - Levenshtein string fuzzy matching and mathematical validation algorithms.

---

## 📁 Related Source Files

- ⚙️ **Main Server Controller**: [backend/app.py](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/backend/app.py)
- 🧠 **PyTorch CNN Model**: [backend/mnist_classifier.py](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/backend/mnist_classifier.py)
- 📐 **OpenCV Grid Detector**: [backend/section_detector.py](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/backend/section_detector.py)
- 🆔 **Metadata Classifier**: [backend/services/header_extraction_service.py](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/backend/services/header_extraction_service.py)
- ✅ **Marks Verifier**: [backend/services/marks_table_extraction_service.py](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/backend/services/marks_table_extraction_service.py)
- 📓 **MNIST Model Training Notebook**: [MNIST (1).ipynb](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/MNIST%20%281%29.ipynb)
