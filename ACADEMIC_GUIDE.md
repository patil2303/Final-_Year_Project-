# 🎓 Academic Project & Viva Presentation Guide
## Local Deep Learning & Computer Vision Document Digitization System

---

## 🏛️ Executive Summary for Academic Submission

This project presents an **On-Device Machine Learning & Computer Vision Document Processing System** designed to extract tabular data, handwritten digits, and structured matrix arrays from photos and PDFs into formatted Excel workbooks (`.xlsx`) and CSV files.

The architecture is **100% Local-First** and operates without external cloud API key requirements:
1. **OpenCV Grayscale Signal Processing**: CLAHE contrast normalization, deskewing, and noise suppression.
2. **OpenCV Morphological Grid Line Extractor**: Horizontal and vertical rectangular kernel line detection ($K_h, K_v$).
3. **Custom Local PyTorch 3-Block CNN**: On-device handwritten digit classification trained on 70,000 MNIST dataset samples achieving **99.55% test accuracy**.
4. **Academic Domain Services**: Student metadata extraction (PRN, Branch Levenshtein normalization) and ink density mark sum verification.

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
                               │ 📐 STEP 2: OPENCV GRID DETECTOR │
                               │ 1. Morphological Kernel Extraction
                               │ 2. Junction Intersection Points │
                               │ 3. Cell Matrix Segmentation     │
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

### Q1: "Is your project reliant on any third-party API key?"
> *"No. The entire digit recognition, table boundary extraction, student metadata processing, and sum verification pipeline runs 100% on-device on our local machine using PyTorch and OpenCV. No external API key is required."*

### Q2: "What is your main algorithmic contribution in this project?"
> *"My primary contribution is a custom 3-block Convolutional Neural Network implemented in PyTorch for handwritten digit classification (`backend/mnist_classifier.py`), combined with OpenCV morphological line kernel extraction (`backend/section_detector.py`) and domain metadata verification services. The model was trained on 70,000 MNIST samples, achieving 99.55% test accuracy."*

### Q3: "Where are the training loss and confusion matrix documented?"
> *"The complete PyTorch training pipeline, epoch loss curves, confusion matrix, and accuracy evaluation code are documented in the Jupyter notebook `MNIST (1).ipynb` in the project root."*

---

## 📁 Key File Locations for Viva Review

- 📓 **Model Training & Loss Curves**: [MNIST (1).ipynb](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/MNIST%20%281%29.ipynb)
- 🎓 **Major Project Guide**: [MAJOR_PROJECT_GUIDE.md](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/MAJOR_PROJECT_GUIDE.md)
- 🧠 **PyTorch CNN Model Architecture**: [mnist_classifier.py](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/backend/mnist_classifier.py)
- 📐 **OpenCV Contour & Line Extractor**: [section_detector.py](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/backend/section_detector.py)
- ⚙️ **Backend Application Server**: [app.py](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/backend/app.py)
