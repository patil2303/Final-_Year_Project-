# 🔑 Gemini API Integration & Purpose Documentation

This document explains why and how the **Photo & PDF to Excel Converter** project utilizes the **Google Gemini Multimodal Vision API key** (`GEMINI_API_KEY`) within the **Multi-Tier Edge-Cloud Hybrid Architecture**.

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

## ✨ Key Capabilities Powered by Gemini Vision API in Hybrid Engine

1. **Flawless Marksheet & Exam Paper Grid Separation**:
   - Correctly identifies complex table headers (`Q.No`, `1a`, `1b`, `1c`, `1d`, `1e`, `1f`, `2a`, `2b`, `3a`, `3b`, `Total`, `Sign of Examiner`).
   - Extracts max marks, awarded marks, parenthesized scores (e.g. `(3)`), fractions (e.g. `11/15`), and examiner signatures without data corruption.

2. **Universal Document Layout Recognition**:
   - Extracts structured grids from **marksheets, invoices, receipts, financial reports, handwritten notes, forms, and multi-page PDFs**.

3. **Strict Structured JSON Output**:
   - Returns standardized JSON data matching the application's interactive spreadsheet format:
     ```json
     {
       "sections": [
         {
           "title": "SECTION 1",
           "headers": ["Q.No", "1a", "1b", "Total", "Sign"],
           "rows": [
             ["2", "2", "2", "20", ""],
             ["1", "2", "2", "11/15", "Bhoj"]
           ]
         }
       ]
     }
     ```

4. **Robust Fallback Mechanism**:
   - If the API key is offline or encounters rate limits, the backend automatically falls back to local OpenCV morphological line kernels + EasyOCR without interrupting user execution.

---

## ⚙️ Environment Configuration

The API key is configured in the root `.env` file:

```env
GEMINI_API_KEY=YOUR_GEMINI_API_KEY_HERE
```

The key is loaded automatically by `backend/gemini_vision_engine.py` during HTTP `/api/extract` requests.
