# 🎓 Major Project Presentation & Defense Documentation
## Automated Document Digitization, Student Metadata Extraction & Marksheet Verification System

---

## 🏛️ Executive Summary

This project has been upgraded to a **Comprehensive Final Year Major Project** for university evaluation. It provides an end-to-end solution for:
1. **Universal Document Digitization & Excel Conversion**: Photo/PDF to formatted `.xlsx` workbooks and CSV files using a **Multi-Tier Edge-Cloud Hybrid Pipeline**.
2. **Student Metadata Extraction**: Extracts PRN, Student Name, Branch, Division, Semester, and Course title using Levenshtein distance fuzzy matching and regex validation (`/api/extract/header`).
3. **Question-Wise Mark Extraction & Sum Verification**: Performs ink density heuristic analysis on handwritten cell crops and validates that question marks sum up correctly to the recorded total score (`/api/extract/marks_verification`).
4. **Interactive Spreadsheet & Metadata UI**: Displays a dedicated **Student Metadata Header Banner** in the browser alongside editable spreadsheet grids and styled Excel downloads.

---

## 🏗️ System Architecture & Services

```text
                                [ Input Document (Photo / PDF) ]
                                               │
                                               ▼
                               ┌───────────────────────────────┐
                               │ 1. Universal Ingestion        │
                               │    • PDF Conversion           │
                               │    • EXIF Auto-Orientation    │
                               └───────────────┬───────────────┘
                                               │
                                               ▼
                               ┌───────────────────────────────┐
                               │ 2. OpenCV Signal Processing   │
                               │    • Grayscale Normalization  │
                               │    • CLAHE Shadow Elimination │
                               │    • Auto-Deskew & Denoising  │
                               └───────────────┬───────────────┘
                                               │
               ┌───────────────────────────────┼───────────────────────────────┐
               ▼                               ▼                               ▼
┌──────────────────────────────┐ ┌──────────────────────────────┐ ┌──────────────────────────────┐
│  Multi-Tier Hybrid Engine    │ │ Header Extraction Service    │ │ Marks Verification Service   │
│ • Gemini Layout Separation   │ │ • Student Name, PRN, Branch  │ │ • Ink Pixel Density Analysis │
│ • Local PyTorch CNN Classifier│ │ • Levenshtein Fuzzy Matching │ │ • Question Score Extraction  │
│   (99.55% Test Accuracy)     │ │ • Regex Validation           │ │ • Sum Verification Engine    │
└──────────────┬───────────────┘ └──────────────┬───────────────┘ └──────────────┬───────────────┘
               │                               │                               │
               └───────────────────────────────┼───────────────────────────────┘
                                               ▼
                              [ Interactive UI & Exporters ]
```

---

## 🌟 Major Project Technical Modules

### 1. Header Metadata Extraction Service (`backend/services/header_extraction_service.py`)
- **PRN Validation**: Strips noise characters, extracting exact digit sequences.
- **Branch Normalization**: Applies Levenshtein distance string matching against known university engineering branches (`IT`, `CSE`, `AIDS`, `AIML`, `EXTC`, `MECHANICAL`, `CIVIL`).
- **Semester & Division Mapping**: Automatically normalizes Roman numerals (`I`, `II`, `III`) to numerical semester indexes (`1`, `2`, `3`).

### 2. Marks Verification & Ink Density Analysis (`backend/services/marks_table_extraction_service.py`)
- **Empty Cell Filtering**: Analyzes dark ink pixel density after margin shaving to distinguish blank exam cells from handwritten digit marks.
- **Mathematical Total Validation**: Checks that individual question scores ($m_{1a} + m_{1b} + \dots + m_{3b}$) match the total cell value.

### 3. PyTorch Deep Learning Classifier (`backend/mnist_classifier.py`)
- **Architecture**: 3 Convolutional Blocks with Batch Normalization, Max Pooling, and Dropout.
- **Accuracy**: **`99.55%`** test accuracy on 70,000 MNIST dataset samples.

---

## 🗣️ Major Project Viva Q&A Cheat Sheet

### Q1: "What makes this suitable for a Major Final Year Project?"
> *"Our project addresses both generalized document digitization and domain-specific university exam mark sheet verification. It combines OpenCV signal processing, a custom PyTorch Convolutional Neural Network (99.55% test accuracy), Gemini Vision AI layout parsing, Levenshtein fuzzy text normalization, and automated mathematical total verification."*

### Q2: "How do you handle background paper noise and shadows?"
> *"We apply Contrast Limited Adaptive Histogram Equalization (CLAHE) across $8 \times 8$ tile grids in OpenCV, followed by bilateral filtering and adaptive thresholding."*

### Q3: "How does the system prevent student PRN misreads?"
> *"PRN extraction uses segmented single-digit bounding box cropping combined with numeric regex whitelisting and length validation."*
