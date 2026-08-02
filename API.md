# 🔑 API & Local Engine Documentation

This document explains the API endpoints and architecture for the **Photo & PDF to Excel Converter** project.

---

## 🎯 On-Device Local Machine Learning Core

The primary goal of this project is to convert photos, scans, and PDFs of document tables, mark sheets, financial statements, and handwritten forms into clean, editable **Excel (`.xlsx`)** and **CSV (`.csv`)** files with production-grade accuracy.

The application runs **100% locally on your computer** without any external cloud API key requirements:

1. **Step 1 (Local Preprocessing - OpenCV)**:
   Converts uploaded images to grayscale ($I_{\text{gray}} = 0.299R + 0.587G + 0.114B$) and applies Contrast Limited Adaptive Histogram Equalization (CLAHE), deskewing, and noise filtering.

2. **Step 2 (Local Grid Detection - OpenCV)**:
   Applies horizontal ($K_h$) and vertical ($K_v$) rectangular morphological line kernels to extract grid bounding box matrix coordinates.

3. **Step 3 (Digit Classification - Local PyTorch CNN)**:
   Single digit and numeric cell crops are evaluated locally using our **custom trained PyTorch 3-Block CNN (`mnist_cnn.pt`)**, achieving **99.55% accuracy** on MNIST digits with Test-Time Augmentation (TTA).

4. **Step 4 (Domain Services)**:
   Extracts student metadata (PRN, Branch Levenshtein normalization) and performs ink density empty cell filtering and mark sum verification.

---

## 🌐 Complete Backend Endpoints List

| Endpoint | HTTP Method | Description |
| :--- | :--- | :--- |
| `/api/upload` | `POST` | Universal file ingestion (PDF, PNG, JPG, WEBP, TIFF, BMP). |
| `/api/extract` | `POST` | Executes 100% Local On-Device PyTorch CNN & OpenCV OCR extraction. |
| `/api/extract/header` | `POST` | Major Project Endpoint: Student metadata extraction (PRN, Name, Branch, Div, Sem). |
| `/api/extract/marks_verification` | `POST` | Major Project Endpoint: Cell ink density check & question mark sum verification. |
| `/api/export/excel` | `POST` | Generates formatted Excel workbook (`.xlsx`). |
| `/api/export/csv` | `POST` | Generates sanitized CSV file (`.csv`). |

---

## ⚙️ Environment Configuration (Optional Cloud API Key)

If you optionally wish to enable cloud layout parsing, configure the key in `.env`:

```env
GEMINI_API_KEY=YOUR_OPTIONAL_GEMINI_API_KEY_HERE
```
