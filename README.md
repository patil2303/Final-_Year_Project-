# 📊 Numbers to Excel & CSV Converter

An automated AI-powered OCR application that converts printed tables, matrix arrays, handwritten digits, and photo notes into clean Excel (`.xlsx`) workbooks and CSV files.

Includes a **custom MNIST-trained 3-block Convolutional Neural Network (CNN)** for high-precision handwritten digit recognition, coupled with automated table/grid structure detection.

---

## 🔥 Features

- 🧠 **MNIST CNN Digit Classifier**: Trained on 70,000 MNIST samples achieving **99.55% test accuracy** for single-digit recognition.
- 📐 **Automated Grid Geometry Detection**: Uses OpenCV contour analysis to locate table boundaries and cell matrices.
- 📄 **Multi-Format Support**: Works with PNG, JPG, JPEG, WEBP, TIFF, BMP, and multi-page PDF documents.
- 📈 **Excel & CSV Export**: Outputs formatted `.xlsx` workbooks with custom header fills, number formatting, and multi-tab section support.
- 🛡️ **Built-in Security**: CSV formula injection protection (`=`, `+`, `-`, `@` sanitization) and 50MB file size limits.
- ✏️ **Interactive In-Browser Spreadsheet Editor**: Review, edit, add rows/columns, and adjust numbers directly in the UI before downloading.

---

## 🏗️ Architecture

```text
[ Document Image / PDF ]
           │
           ▼
[ Universal Image Processor ] ── (Grayscale, CLAHE, Deskew, Denoise)
           │
           ▼
[ Grid Contour & Box Detector ]
      │               │
  (Grid Mode)   (Freeform Mode)
      │               │
      └───────┬───────┘
              ▼
[ Two-Tier Digit Recognizer ]
   ├── Tier 1: MNIST CNN Classifier (99.55% accuracy, fast)
   └── Tier 2: EasyOCR + CLAHE Fallback (for complex freeform text)
              │
              ▼
[ Section & Matrix Builder ]
              │
              ▼
[ Interactive UI / Excel & CSV Exporters ]
```

---

## 🚀 Quick Start

### 1. Prerequisites & Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/SHREYASPATIL2005/Numbers-to-Excel.git
cd Numbers-to-Excel

pip install -r requirements.txt
```

### 2. Run the Application

```bash
python run.py
```

The application server will start at `http://127.0.0.1:8000` and automatically open your default web browser.

---

## 📂 Project Structure

```text
Numbers-to-Excel/
├── backend/
│   ├── app.py                 # FastAPI Web Server & Endpoint Handlers
│   ├── mnist_classifier.py    # PyTorch CNN Model Architecture & Classifier
│   ├── ocr_engine.py          # Two-Tier OCR Recognition Engine
│   ├── section_detector.py    # Document Structure & Matrix Segmentation
│   ├── data_formatter.py      # Styled Excel & CSV Exporters
│   ├── utils.py               # Image Preprocessing & Format Utilities
│   └── models/
│       └── mnist_cnn.pt       # Pre-trained CNN Model Weights (99.55% Acc)
├── static/
│   ├── index.html             # Web Application HTML Interface
│   ├── css/style.css          # Modern UI Design & Glassmorphism Styling
│   └── js/
│       ├── app.js             # Client UI Event & Upload Controller
│       └── spreadsheet_editor.js # Editable Grid Controller
├── sample_images/             # Demonstration & Sample Tables
├── .gitignore
├── README.md
└── run.py                     # Main Server Launcher Script
```

---

## 📊 Model Performance

| Metric | Score |
| :--- | :--- |
| **Accuracy** | **`99.55%`** |
| **Precision** | **`0.9955`** |
| **Recall** | **`0.9955`** |
| **F1-Score** | **`0.9955`** |
| **Inference Time** | `< 2 ms` per cell crop |

---

## 📜 License

MIT License. Free for academic, personal, and commercial use.
