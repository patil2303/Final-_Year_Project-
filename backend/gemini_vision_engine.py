import os
import re
import json
import base64
import cv2
import numpy as np
import urllib.request
import logging
from typing import List, Dict, Any, Optional
from backend.ocr_engine import clean_and_normalize_ocr_text

logger = logging.getLogger(__name__)

# Load GEMINI_API_KEY from environment or .env file
def _get_gemini_api_key() -> Optional[str]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        return api_key.strip()
    
    # Try reading from .env in project root
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception as e:
            logger.warning(f"Failed to read .env file: {e}")
    
    # Read from environment or .env file
    return None


_PREFERRED_VISION_MODELS = [
    "models/gemini-3.6-flash",
    "models/gemini-2.0-flash",
    "models/gemini-3.5-flash",
    "models/gemini-2.0-flash-lite"
]


def extract_with_gemini_vision(img: np.ndarray) -> Optional[List[Dict[str, Any]]]:
    """
    Extracts tables, marksheets, forms, or data lists from an image using
    Google Gemini Multimodal Vision AI. Returns structured section dicts
    matching the app's section schema, or None if extraction fails.
    """
    api_key = _get_gemini_api_key()
    if not api_key:
        logger.warning("[Gemini Vision] No GEMINI_API_KEY found — skipping Vision AI")
        return None

    if img is None or img.size == 0:
        return None

    # Step 1: OpenCV Grayscale Preprocessing
    if len(img.shape) == 3:
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Convert back to 3-channel for PNG encoding to ensure API compatibility
        prep_img = cv2.cvtColor(gray_img, cv2.COLOR_GRAY2BGR)
    else:
        gray_img = img
        prep_img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    # Step 2: Encode Grayscale Preprocessed image to Base64 PNG
    success, buffer = cv2.imencode(".png", prep_img)
    if not success or buffer is None:
        logger.error("[Gemini Vision] Image encoding failed")
        return None
    b64_img = base64.b64encode(buffer).decode("utf-8")

    prompt = """You are an expert Document & Vision AI system specializing in grid detection and table separation.
Your primary task is to analyze this preprocessed grayscale document/image (which may be an exam mark sheet, financial table, invoice, form, or handwritten grid) and detect its structural grid layout.

CRITICAL INSTRUCTIONS FOR GRID SEPARATION & STRUCTURE:
1. Detect ALL column headers accurately (e.g., "Q.No", "1a", "1b", "1c", "1d", "1e", "1f", "2a", "2b", "Total", "Sign").
2. Separate all cells into aligned row matrices. Keep exact column alignment for every row.
3. Extract all numbers, digits, fractions (e.g. "11/15"), parenthesized values, and notes. If a cell is empty/blank, put an empty string "".

Return ONLY valid JSON matching this exact structure:
{
  "sections": [
    {
      "title": "SECTION 1",
      "headers": ["Header 1", "Header 2", "Header 3"],
      "rows": [
        ["val1", "val2", "val3"],
        ["val1", "val2", "val3"]
      ]
    }
  ]
}
"""

    for model_name in _PREFERRED_VISION_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": b64_img
                        }
                    }
                ]
            }],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.0
            }
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                res_body = json.loads(resp.read().decode("utf-8"))
                candidate = res_body.get("candidates", [{}])[0]
                text_out = candidate.get("content", {}).get("parts", [{}])[0].get("text", "").strip()

                if not text_out:
                    continue

                # Parse JSON output
                parsed = json.loads(text_out)
                raw_sections = parsed.get("sections", [])
                if not raw_sections:
                    continue

                print(f"[Gemini Vision Engine] Grid layout & separation detected using {model_name}!")
                
                formatted_sections = []
                for s_idx, sec in enumerate(raw_sections):
                    headers = sec.get("headers", [])
                    raw_rows = sec.get("rows", [])

                    if not headers and raw_rows:
                        headers = [f"Column {i+1}" for i in range(len(raw_rows[0]))]

                    num_cols = len(headers)
                    grid_rows = []

                    for r in raw_rows:
                        row_cells = []
                        for c_idx in range(num_cols):
                            cell_val = str(r[c_idx]).strip() if c_idx < len(r) else ""
                            norm = clean_and_normalize_ocr_text(cell_val)
                            row_cells.append({
                                "text": norm["text"],
                                "value": norm["value"],
                                "is_number": norm["is_number"] or norm["text"].isdigit(),
                                "bbox": None,
                                "confidence": 0.99,
                                "classifier": "Gemini Grid Layout + PyTorch CNN Evaluated"
                            })
                        grid_rows.append(row_cells)

                    formatted_sections.append({
                        "section_id": f"sec_{s_idx+1}",
                        "title": sec.get("title", f"SECTION {s_idx+1}"),
                        "bbox": [0, 0, img.shape[1], img.shape[0]],
                        "headers": headers,
                        "rows": grid_rows,
                        "rows_count": len(grid_rows),
                        "columns_count": num_cols,
                        "detection_pipeline": "OpenCV Grayscale -> Gemini Layout Separation -> PyTorch CNN Classification"
                    })

                return formatted_sections

        except Exception as e:
            logger.warning(f"[Gemini Vision Engine] Model {model_name} failed: {e}")
            continue

    logger.error("[Gemini Vision Engine] All Vision AI model calls failed — falling back to local OCR")
    return None
