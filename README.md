# 📊 Numbers to Excel & CSV Converter

An automated AI-powered document digitization application that converts printed tables, exam mark sheets, matrix arrays, handwritten digits, and photo notes into formatted Excel (`.xlsx`) workbooks and CSV files.

Powered by a **Multi-Tier Edge-Cloud Hybrid Engine**:
- **OpenCV Grayscale Image Preprocessing** (CLAHE, Deskew, Denoise)
- **Google Gemini Vision AI** (Structural Grid Layout & Table Separation)
- **Custom Local PyTorch 3-Block CNN** (Handwritten & Printed Digit Classification, 99.55% Accuracy)
- **Student & Marksheet Metadata Services** (PRN, Branch, Division, Semester, Ink Density Filtering, Sum Verification)

---

## 🔥 Key Features

- ⚡ **Multi-Tier Edge-Cloud Hybrid Engine**: Combines cloud layout separation with on-device PyTorch deep learning digit classification.
- 🧠 **MNIST PyTorch CNN Classifier**: Trained on 70,000 MNIST dataset samples achieving **99.55% test accuracy** for single-digit recognition.
- 👤 **Student & Marksheet Metadata Extraction**: Extracts PRN, Student Name, Branch (using Levenshtein fuzzy string matching), Division, and Semester.
- ✅ **Automated Mark Verification**: Calculates cell ink pixel density and verifies question marks sum up correctly to the recorded total score.
- 📐 **Automated Grid Geometry & Layout Separation**: Identifies column headers, row matrices, and table boundaries.
- 📄 **Multi-Format Support**: Processes PNG, JPG, JPEG, WEBP, TIFF, BMP, and multi-page PDF documents.
- 📈 **Styled Excel & CSV Export**: Outputs formatted `.xlsx` workbooks with custom header styling, number formatting, and multi-tab support.
- ✏️ **Interactive In-Browser Spreadsheet Editor**: Review, edit, add/delete rows and columns directly in the browser UI with an integrated **Student Metadata Banner**.
- 🎓 **Academic Viva & Major Project Ready**: Fully documented for university project defense ([MAJOR_PROJECT_GUIDE.md](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/MAJOR_PROJECT_GUIDE.md), [ACADEMIC_GUIDE.md](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/ACADEMIC_GUIDE.md), and [Hybrid.md](file:///c:/Users/shrey/OneDrive/Desktop/NUMBERS%20TO%20EXCEL%20-%20Copy%20-%20Copy/Hybrid.md)).

---

## 🏗️ Architecture

```text
[ Document Image / PDF ]
           │
           ▼
[ Step 1: OpenCV Image Processor ] ────── (Grayscale Conversion, CLAHE, Deskew, Denoise)
           │
           ▼
[ Step 2: Gemini Vision AI ] ──────────── (Grid Layout Parsing & Table Matrix Separation)
           │
           ▼
[ Step 3: Custom PyTorch CNN ] ────────── (Digit Classification & TTA Majority Voting)
           │
           ├──────────────────────────────┐
           ▼                              ▼
[ Section & Matrix Builder ]    [ Student Metadata & Sum Verifier ]
           │                              │
           └──────────────┬───────────────┘
                          ▼
[ Interactive UI / Metadata Banner / Excel & CSV Exporters ]
```

---

## 🚀 Quick Start

### 1. Prerequisites & Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/SHREYASPATIL2005/NUM-TO-EXCEL-PART-2.git
cd NUM-TO-EXCEL-PART-2

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
NUM-TO-EXCEL-PART-2/
├── backend/
│   ├── app.py                 # FastAPI Web Server & Endpoint Handlers
│   ├── gemini_vision_engine.py# Gemini Layout & Grid Separation Engine
│   ├── mnist_classifier.py    # PyTorch CNN Model Architecture & Classifier
│   ├── ocr_engine.py          # Two-Tier OCR Recognition Engine
│   ├── section_detector.py    # Document Structure & Matrix Segmentation
│   ├── data_formatter.py      # Styled Excel & CSV Exporters
│   ├── utils.py               # Image Preprocessing & Format Utilities
│   ├── services/              # Major Project Domain Services
│   │   ├── header_extraction_service.py # Student Metadata & Fuzzy Levenshtein Matcher
│   │   ├── marks_table_extraction_service.py # Ink Density & Total Score Verifier
│   │   └── preprocessing_service.py # Multi-Thresholding Variant Processor
│   └── models/
│       └── mnist_cnn.pt       # Pre-trained CNN Model Weights (99.55% Acc)
├── static/
│   ├── index.html             # Web Application HTML Interface with Metadata Banner
│   ├── css/style.css          # Modern UI Design & Glassmorphism Styling
│   └── js/
│       ├── app.js             # Client UI Event & Upload Controller
│       └── spreadsheet_editor.js # Editable Grid Controller
├── sample_images/             # Demonstration & Sample Tables
├── tests/                     # Automated Integration & Engine Tests
├── Hybrid.md                  # Detailed Hybrid Engine Architecture Guide
├── MAJOR_PROJECT_GUIDE.md     # Comprehensive Final Year Major Project Guide
├── ACADEMIC_GUIDE.md          # Viva Presentation & Examination Defense Guide
├── API.md                     # Vision API Key & Purpose Documentation
├── WORKFLOW.md                # End-to-End System Workflow
├── README.md
└── run.py                     # Main Server Launcher Script
```

---

## 📊 Model Performance

| Metric | Score |
| :--- | :--- |
| **Test Accuracy** | **`99.55%`** |
| **Precision** | **`0.9955`** |
| **Recall** | **`0.9955`** |
| **F1-Score** | **`0.9955`** |
| **Local Inference Time** | `< 2 ms` per cell crop |

---

## 📜 License

MIT License. Free for academic, personal, and commercial use.
