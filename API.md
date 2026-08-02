# 🔑 API Integration & Endpoints Purpose Documentation

This document explains the API endpoints and integration purpose for the **Photo & PDF to Excel Converter** project within the **Multi-Tier Edge-Cloud Hybrid Architecture**.

---

## 🎯 Role & Purpose of Gemini API Key in the Hybrid Pipeline

The primary goal of this project is to convert photos, scans, and PDFs of document tables, mark sheets, financial statements, and handwritten forms into clean, editable **Excel (`.xlsx`)** and **CSV (`.csv`)** files with production-grade accuracy.

In our **Hybrid Engine**, the workload is split between local computer vision / deep learning models and cloud vision AI:

1. **Step 1 (Local Preprocessing - OpenCV)**:
   Converts uploaded images to grayscale ($I_{\text{gray}} = 0.299R + 0.587G + 0.114B$) and applies Contrast Limited Adaptive Histogram Equalization (CLAHE), deskewing, and noise filtering.

2. **Step 2 (Layout & Grid Separation - Gemini Vision AI)**:
   The preprocessed grayscale image is passed to Gemini Vision AI to perform **zero-shot document layout parsing**:
   - Detects complex table boundaries, paper folds, and skewed grid cells.
   - Extracts column header names (`Q.No`, `1a`, `1b`, `1c`, `Total`, `Marks`, `Sign`).
   - Aligns cells into clean row and column matrices.

3. **Step 3 (Digit Classification - Local PyTorch CNN)**:
   Single digit and numeric cell crops are evaluated locally using our **custom trained PyTorch 3-Block CNN (`mnist_cnn.pt`)**, achieving **99.55% accuracy** on MNIST digits with Test-Time Augmentation (TTA).

---

## 🌐 Complete Backend Endpoints List

| Endpoint | HTTP Method | Description |
| :--- | :--- | :--- |
| `/api/upload` | `POST` | Universal file ingestion (PDF, PNG, JPG, WEBP, TIFF, BMP). |
| `/api/extract` | `POST` | Executes Hybrid Edge-Cloud OCR table extraction. |
| `/api/extract/header` | `POST` | Major Project Endpoint: Student metadata extraction (PRN, Name, Branch, Div, Sem). |
| `/api/extract/marks_verification` | `POST` | Major Project Endpoint: Cell ink density check & question mark sum verification. |
| `/api/export/excel` | `POST` | Generates formatted Excel workbook (`.xlsx`). |
| `/api/export/csv` | `POST` | Generates sanitized CSV file (`.csv`). |

---

## ⚙️ Environment Configuration

The API key is configured in the root `.env` file:

```env
GEMINI_API_KEY=YOUR_GEMINI_API_KEY_HERE
```

The key is loaded automatically by `backend/gemini_vision_engine.py` during HTTP `/api/extract` requests.
