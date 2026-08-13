# 🎓 Academic Marksheet Digitizer & Master Grading Portal

An AI-powered document digitization and academic marksheet evaluation system that converts printed and handwritten exam marksheets, matrix tables, and student answer sheets into structured **MongoDB Atlas** records and consolidated master **Excel (`.xlsx`) & CSV** grade workbooks.

Built with **FastAPI**, **PyTorch CNN (99.55% Acc)**, **Google Gemini Multimodal Vision AI**, and **MongoDB Atlas**.

---

## 🔥 Key Features

- 🎓 **Dual-Role Portal Architecture**:
  - **Student Portal**: Mobile-first interface with camera capture (`capture="environment"`), AI marksheet extraction, interactive metadata editing (Name, PRN, Roll No, Branch, Division, Semester, Subject), and one-click database submission.
  - **Faculty Master Dashboard**: Administrative management console to create classes/exams, monitor live submission statistics in real-time, search student rosters, and download consolidated Master Class Excel sheets.
- ⚡ **Multi-Tier Edge-Cloud Hybrid Vision Engine**:
  - Cloud layout detection (Google Gemini Flash) to isolate table structures with zero cell hallucination.
  - Local custom PyTorch 3-Block CNN (trained on 70,000 MNIST samples with 99.55% test accuracy) for instantaneous on-device digit classification.
- 🍃 **MongoDB Atlas Cloud Integration**:
  - Centralized storage for registered academic batches and verified student answer sheets.
  - **Smart Upsert Protection**: Prevents duplicate rows when a student re-submits a cleaner photo.
  - **Natural Numeric Roll Number Sorting**: Automatically extracts numeric indices from composite roll formats (e.g., `44 / SE`, `SE-46`, `B-63`) to order rosters systematically ($44 \rightarrow 46 \rightarrow 63$).
- 📊 **Consolidated Master Class Grade Sheet Compiler**:
  - Aggregates all submissions in a classroom into a single unified Excel spreadsheet formatted with exam headers, maximum question marks, and student breakdown.
- 📱 **100% Mobile-Friendly & Responsive**:
  - One-tap mobile camera snap button, touch-friendly inputs, auto-zoom prevention for iOS, and animated horizontal scroll indicators for data tables.

---

## 🏗️ Architecture & Workflow

```text
[ Mobile Camera / Image / PDF ]
              │
              ▼
[ OpenCV Image Preprocessor ] ─── (Grayscale, CLAHE, Deskew, Denoise)
              │
              ▼
[ Gemini Multimodal Vision AI ] ── (Isolates Mark Table & Header Metadata)
              │
              ▼
[ Custom PyTorch CNN (99.55%) ] ── (Digit Recognition & Sum Verification)
              │
              ▼
[ Interactive Web UI ] ────────── (Student Review, Live Editing, Instant Correction)
              │
              ▼
[ MongoDB Atlas Database ] ────── (Smart Upsert & Natural Numeric Roll Sorting)
              │
              ▼
[ Master Excel & CSV Compiler ] ── (Consolidated Multi-Student Class Workbook)
```

---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/patil2303/Final-_Year_Project-.git
cd Final-_Year_Project-
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the root directory (or copy from `.env.example`):

```ini
GEMINI_API_KEY=your_gemini_api_key_here
MONGODB_URI=mongodb+srv://<username>:<password>@cluster0.dbplhay.mongodb.net/exam_grading_portal?retryWrites=true&w=majority&appName=Cluster0
```

### 4. Run the Application

```bash
python run.py
```

The application server will start at `http://127.0.0.1:8000`.

---

## 📂 Project Structure

```text
NUM-TO-EXCEL-PART-2/
├── backend/
│   ├── app.py                         # FastAPI Web Server & REST Endpoints
│   ├── database/
│   │   └── mongo.py                   # MongoDB Atlas Client, Collections & Indexes
│   ├── services/
│   │   ├── submission_service.py      # Classroom Management, Upsert & Master Excel Compiler
│   │   ├── header_extraction_service.py # Fuzzy Levenshtein & Metadata Extraction
│   │   ├── marks_table_extraction_service.py # Ink Density & Total Score Verifier
│   │   └── preprocessing_service.py   # Multi-Threshold Image Processor
│   ├── gemini_vision_engine.py        # Gemini Multimodal Vision Pipeline
│   ├── mnist_classifier.py            # PyTorch 3-Block CNN (99.55% Acc)
│   ├── section_detector.py            # Table Structure & Matrix Segmentation
│   └── data_formatter.py              # Openpyxl Excel & CSV Exporter
├── static/
│   ├── index.html                     # Dual Portal HTML (Student & Faculty Dashboard)
│   ├── css/style.css                  # Responsive Glassmorphism & Mobile Touch Styles
│   └── js/
│       ├── app.js                     # Dual Portal Controller & MongoDB Synced Client
│       └── spreadsheet_editor.js      # In-Browser Grid Controller
├── sample_images/                     # Test Marksheets & Document Photos
├── requirements.txt                   # Python Dependencies
├── .env.example                       # Environment Configuration Template
├── README.md
└── run.py                             # Main Server Launcher Script
```

---

## 📜 License

MIT License. Free for academic, personal, and educational use.
