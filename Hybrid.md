# ⚡ Multi-Tier Edge-Cloud Hybrid Pipeline Documentation

---

## 🏛️ System Architecture Overview

The **Hybrid Pipeline** is a state-of-the-art **Multi-Tier Edge-Cloud Document Processing Engine**. It combines **OpenCV Image Processing**, **Google Gemini Multimodal Vision AI** (for layout & grid separation), and a **Custom Local PyTorch 3-Block CNN** (for digit recognition).

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
│  STEP 2: Gemini Vision AI Grid & Layout Detector │
│  - Document layout parsing                       │
│  - Table boundary & column header extraction     │
│  - Cell matrix alignment & separation            │
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

### 2. STEP 2: Structural Grid Detection & Table Separation (Gemini Vision AI)
- The preprocessed grayscale image is passed to the Multimodal Vision AI model.
- **Role of Gemini Vision AI**:
  - Identifies document structure (exam mark sheets, financial invoices, matrices, forms).
  - Detects column header names (e.g. `Q.No`, `1a`, `1b`, `Total`, `Marks`).
  - Separates table boundaries into aligned row and column grid matrices.
  - Generates structured JSON schema containing row cell entries.

### 3. STEP 3: Digit Recognition via Custom PyTorch CNN Model
- For all single-digit and numeric cell crops within the detected grid, the system runs local deep learning inference using our pre-trained PyTorch model (`backend/models/mnist_cnn.pt`).
- **PyTorch Model Architecture**:
  - **Conv Block 1**: `Conv2d(1, 32, k=3, p=1) -> BatchNorm2d -> ReLU -> Conv2d(32, 32, 3) -> BatchNorm2d -> ReLU -> MaxPool2d(2, 2) -> Dropout(0.25)`
  - **Conv Block 2**: `Conv2d(32, 64, k=3, p=1) -> BatchNorm2d -> ReLU -> Conv2d(64, 64, 3) -> BatchNorm2d -> ReLU -> MaxPool2d(2, 2) -> Dropout(0.25)`
  - **Dense Layer**: `Linear(64 * 5 * 5, 256) -> BatchNorm1d -> ReLU -> Dropout(0.5) -> Linear(256, 10)`
- **Test-Time Augmentation (TTA)**:
  If initial CNN confidence is below $0.55$, the engine generates 5 augmented crops (rotated, shifted, scaled) and performs majority voting for maximum classification robustness.

---

## 🎯 Why This Hybrid Pipeline Is Ideal for Academic Submission

1. **Demonstrates Real Engineering Work**:
   - Your custom trained PyTorch CNN model performs local digit recognition.
   - OpenCV handles image signal processing and grayscale transformations.
2. **Solves Complex Real-World Document Layouts**:
   - Cloud Multimodal AI handles irregular layouts, tilted mark sheets, and freeform tables.
3. **Best of Both Worlds**:
   - Combine high-level vision layout parsing with on-device deep learning classification.

---

## 📁 Related Source Files

- ⚙️ **Hybrid Pipeline Controller**: [backend/app.py](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/backend/app.py)
- 🧠 **PyTorch CNN Model**: [backend/mnist_classifier.py](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/backend/mnist_classifier.py)
- 🌐 **Grayscale & Grid Engine**: [backend/gemini_vision_engine.py](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/backend/gemini_vision_engine.py)
- 📓 **MNIST Model Training Notebook**: [MNIST (1).ipynb](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/MNIST%20%281%29.ipynb)
