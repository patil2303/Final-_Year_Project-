# 🎓 Academic Project & Viva Presentation Guide
## Multi-Tier Edge-Cloud Hybrid Document Digitization System

---

## 🏛️ Executive Summary for Academic Submission

This project presents a **Multi-Tier Edge-Cloud Hybrid Document Processing System** designed to extract tabular data, handwritten digits, and structured matrix arrays from photos and PDFs into formatted Excel workbooks (`.xlsx`) and CSV files.

The architecture combines:
1. **OpenCV Grayscale Signal Processing**: CLAHE contrast normalization, deskewing, and noise suppression.
2. **Google Gemini Multimodal Vision AI**: Structural table layout parsing, column header detection, and row cell matrix separation.
3. **Custom Local PyTorch 3-Block CNN**: On-device handwritten digit classification trained on 70,000 MNIST dataset samples achieving **99.55% test accuracy**.
4. **Domain Services**: Student metadata extraction (PRN, Branch Levenshtein normalization) and ink density mark sum verification.

---

## 🏗️ Architectural Overview

```text
                                 [ Input Document (Photo / PDF) ]
                                                │
                                                ▼
                                [ Universal Image Preprocessor ]
                       (Grayscale, CLAHE Histogram Equalization, Deskew)
                                                │
                                                ▼
                               ┌─────────────────────────────────┐
                               │ ☁️ STEP 2: GEMINI VISION AI    │
                               │    (Grid & Layout Separation)   │
                               │ 1. Document Layout Parsing      │
                               │ 2. Table Boundary Detection     │
                               │ 3. Header Extraction            │
                               │ 4. Matrix Cell Separation       │
                               └────────────────┬────────────────┘
                                                │
                                                ▼
                               ┌─────────────────────────────────┐
                               │ 🧠 STEP 3: CUSTOM PYTORCH CNN   │
                               │    (Local Digit Classifier)     │
                               │ 1. PyTorch 3-Block CNN Model    │
                               │    (99.55% Test Accuracy)       │
                               │ 2. TTA Majority Voting          │
                               │ 3. Local EasyOCR Fallback       │
                               └────────────────┬────────────────┘
                                                │
                                                ▼
                               ┌─────────────────────────────────┐
                               │ 🆔 STEP 4: DOMAIN SERVICES      │
                               │ 1. Student Metadata Extractor   │
                               │ 2. Levenshtein Branch Matcher   │
                               │ 3. Mark Sum Verifier            │
                               └────────────────┬────────────────┘
                                                │
                                                ▼
                                [ Interactive Editor & Exporters ]
```

---

## 🧠 1. Custom Local Machine Learning & CV Pipeline

### A. Preprocessing & Grayscale Normalization (`backend/utils.py`)
- **Grayscale Conversion**:
  $$I_{\text{gray}} = 0.299R + 0.587G + 0.114B$$
- **CLAHE (Contrast Limited Adaptive Histogram Equalization)**:
  Enhances local contrast across small $(8 \times 8)$ image tiles, making faint pencil marks or faded ink clearly visible.

### B. Custom PyTorch Convolutional Neural Network (`backend/mnist_classifier.py`)
- **Training Dataset**: MNIST (70,000 labeled handwritten digit samples).
- **Architecture**:
  - **Conv Block 1**: `Conv2d(1, 32, kernel=3, padding=1) -> BatchNorm2d -> ReLU -> Conv2d(32, 32, 3) -> BatchNorm2d -> ReLU -> MaxPool2d(2, 2) -> Dropout(0.25)`
  - **Conv Block 2**: `Conv2d(32, 64, kernel=3, padding=1) -> BatchNorm2d -> ReLU -> Conv2d(64, 64, 3) -> BatchNorm2d -> ReLU -> MaxPool2d(2, 2) -> Dropout(0.25)`
  - **Fully Connected**: `Linear(64*5*5, 256) -> BatchNorm1d -> ReLU -> Dropout(0.5) -> Linear(256, 10)`
- **Evaluation Metrics**:
  - **Accuracy**: **`99.55%`**
  - **Precision / Recall / F1-Score**: **`0.9955`**
  - **Inference Time**: `< 2 ms` per cell crop on local CPU.

---

## 🗣️ Sample Viva Examination Questions & Answers

### Q1: "What is your main algorithmic contribution in this project?"
> *"My primary contribution is a custom 3-block Convolutional Neural Network implemented in PyTorch for handwritten digit classification (`backend/mnist_classifier.py`), combined with OpenCV signal preprocessing and domain metadata verification services. The model was trained on 70,000 MNIST samples, achieving 99.55% test accuracy."*

### Q2: "How does the system handle irregular or skewed table layouts?"
> *"We use OpenCV deskewing and CLAHE adaptive contrast enhancement followed by Gemini Vision AI layout parsing. Gemini detects table boundaries and column alignment, and individual cell crops are evaluated using our local PyTorch CNN classifier with Test-Time Augmentation (TTA)."*

### Q3: "Where are the training loss and confusion matrix documented?"
> *"The complete PyTorch training pipeline, epoch loss curves, confusion matrix, and accuracy evaluation code are documented in the Jupyter notebook `MNIST (1).ipynb` in the project root."*

---

## 📁 Key File Locations for Viva Review

- 📓 **Model Training & Loss Curves**: [MNIST (1).ipynb](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/MNIST%20%281%29.ipynb)
- 🎓 **Major Project Guide**: [MAJOR_PROJECT_GUIDE.md](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/MAJOR_PROJECT_GUIDE.md)
- ⚡ **Hybrid Engine Workflow**: [Hybrid.md](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/Hybrid.md)
- 🧠 **PyTorch CNN Model Architecture**: [mnist_classifier.py](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/backend/mnist_classifier.py)
- 🌐 **Grayscale & Layout Engine**: [gemini_vision_engine.py](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/backend/gemini_vision_engine.py)
- ⚙️ **Backend Application Server**: [app.py](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/backend/app.py)
