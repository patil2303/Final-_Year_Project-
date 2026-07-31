import io
import os
import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Maximum upload file size: 50 MB
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024

from backend.utils import (
    universal_file_to_cv2_images,
    base64_to_cv2,
    cv2_to_base64,
    bytes_to_cv2,
    cv2_to_bytes,
    preprocess_image,
    crop_roi
)
from backend.ocr_engine import run_ocr_on_image
from backend.section_detector import detect_sections_and_tables
from backend.data_formatter import export_to_excel_bytes, export_to_csv_string

app = FastAPI(
    title="Photo & PDF to Excel Converter API",
    description="API for extracting tables, matrix arrays, numbers, and handwritten notes from photos and PDFs into Excel and CSV sheets."
)

# Serve static files
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
def read_root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Photo & PDF to Excel Server Running</h1>"

class PreprocessRequest(BaseModel):
    image_b64: str
    contrast: float = 1.0
    brightness: float = 1.0
    binarize: bool = False
    auto_deskew: bool = False
    denoise: bool = False

class ExtractRequest(BaseModel):
    image_b64: Optional[str] = None
    file_b64_list: Optional[List[str]] = None
    roi: Optional[Dict[str, int]] = None  # {x, y, width, height}
    contrast: float = 1.0
    brightness: float = 1.0
    binarize: bool = False
    auto_deskew: bool = False
    denoise: bool = False

class ExportRequest(BaseModel):
    sections: List[Dict[str, Any]]

@app.post("/api/upload")
async def upload_file_endpoint(file: UploadFile = File(...)):
    """
    Accepts ANY file upload format (PNG, JPG, JPEG, PDF, WEBP, TIFF, BMP, HEIC).
    Converts and returns image previews and page counts.
    """
    try:
        contents = await file.read()
        if len(contents) > _MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum allowed size is {_MAX_UPLOAD_BYTES // (1024*1024)} MB."
            )
        filename = file.filename or "file.png"
        
        cv2_imgs = universal_file_to_cv2_images(contents, filename)
        if not cv2_imgs:
            raise HTTPException(status_code=400, detail="Could not process file format. Please try another image or PDF file.")

        pages_b64 = [cv2_to_base64(img) for img in cv2_imgs]
        h, w = cv2_imgs[0].shape[:2]

        return {
            "status": "success",
            "filename": filename,
            "total_pages": len(cv2_imgs),
            "width": w,
            "height": h,
            "image_b64": pages_b64[0],
            "pages_b64": pages_b64
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Upload processing failed")
        raise HTTPException(status_code=500, detail="An error occurred while processing the uploaded file.")

@app.post("/api/preprocess")
def preprocess_endpoint(req: PreprocessRequest):
    """Applies real-time contrast, brightness, binarization, deskewing filters."""
    try:
        img = base64_to_cv2(req.image_b64)
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image data.")

        processed = preprocess_image(
            img,
            contrast=req.contrast,
            brightness=req.brightness,
            binarize=req.binarize,
            auto_deskew=req.auto_deskew,
            denoise=req.denoise
        )

        h, w = processed.shape[:2]
        processed_b64 = cv2_to_base64(processed)

        return {
            "status": "success",
            "width": w,
            "height": h,
            "processed_b64": processed_b64
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Preprocessing failed")
        raise HTTPException(status_code=500, detail="An error occurred during image preprocessing.")

@app.post("/api/extract")
def extract_sections(req: ExtractRequest):
    """Executes OCR digit extraction and automated section/table segmentation."""
    try:
        target_imgs = []
        if req.file_b64_list and len(req.file_b64_list) > 0:
            for b64 in req.file_b64_list:
                img = base64_to_cv2(b64)
                if img is not None:
                    target_imgs.append(img)
        elif req.image_b64:
            img = base64_to_cv2(req.image_b64)
            if img is not None:
                target_imgs.append(img)

        if not target_imgs:
            raise HTTPException(status_code=400, detail="No valid image data provided for extraction.")

        all_sections = []
        all_ocr_tokens = []

        for p_idx, raw_img in enumerate(target_imgs):
            # Apply preprocessing
            processed = preprocess_image(
                raw_img,
                contrast=req.contrast,
                brightness=req.brightness,
                binarize=req.binarize,
                auto_deskew=req.auto_deskew,
                denoise=req.denoise
            )

            # Crop ROI if specified (on page 1)
            if p_idx == 0 and req.roi and req.roi.get("width", 0) > 10 and req.roi.get("height", 0) > 10:
                t_img = crop_roi(
                    processed,
                    req.roi["x"],
                    req.roi["y"],
                    req.roi["width"],
                    req.roi["height"]
                )
            else:
                t_img = processed

            # Run OCR
            ocr_tokens = run_ocr_on_image(t_img)

            # Detect sections & table grids for this page
            p_sections = detect_sections_and_tables(ocr_tokens, t_img.shape)

            # Add page prefix if multi-page
            for s in p_sections:
                if len(target_imgs) > 1:
                    s["title"] = f"Page {p_idx+1} - {s['title']}"
                all_sections.append(s)

            all_ocr_tokens.extend(ocr_tokens)

        return {
            "status": "success",
            "total_tokens": len(all_ocr_tokens),
            "total_sections": len(all_sections),
            "sections": all_sections,
            "ocr_tokens": all_ocr_tokens
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("OCR extraction failed")
        raise HTTPException(status_code=500, detail="An error occurred during number extraction.")

@app.post("/api/export/excel")
def export_excel_endpoint(req: ExportRequest):
    """Generates and downloads styled Excel (.xlsx) workbook."""
    try:
        excel_bytes = export_to_excel_bytes(req.sections)
        headers = {
            'Content-Disposition': 'attachment; filename="extracted_numbers_tables.xlsx"'
        }
        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers
        )
    except Exception as e:
        logger.exception("Excel export failed")
        raise HTTPException(status_code=500, detail="An error occurred while generating the Excel file.")

@app.post("/api/export/csv")
def export_csv_endpoint(req: ExportRequest):
    """Generates and downloads clean CSV (.csv) file."""
    try:
        csv_str = export_to_csv_string(req.sections)
        headers = {
            'Content-Disposition': 'attachment; filename="extracted_numbers_tables.csv"'
        }
        return Response(
            content=csv_str.encode('utf-8'),
            media_type="text/csv",
            headers=headers
        )
    except Exception as e:
        logger.exception("CSV export failed")
        raise HTTPException(status_code=500, detail="An error occurred while generating the CSV file.")
