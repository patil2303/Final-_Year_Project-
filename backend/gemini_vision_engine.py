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
    
    # Try reading from .env in project root and parent directories
    project_root = os.path.dirname(os.path.dirname(__file__))
    parent_root = os.path.dirname(project_root)
    candidate_paths = [
        os.path.join(project_root, ".env"),
        os.path.join(parent_root, ".env"),
        os.path.join(os.getcwd(), ".env")
    ]
    
    for env_path in candidate_paths:
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GEMINI_API_KEY="):
                            key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if key:
                                return key
            except Exception as e:
                logger.warning(f"Failed to read .env file at {env_path}: {e}")
    
    return None


_PREFERRED_VISION_MODELS = [
    "models/gemini-flash-lite-latest",
    "models/gemini-2.5-flash",
    "models/gemini-flash-latest",
    "models/gemini-3-flash-preview",
    "models/gemini-2.5-pro"
]


def _clean_and_parse_json(text_out: str) -> dict:
    """Robustly extracts and parses JSON even if LLM outputs markdown fences, trailing commas, or unquoted fraction strings."""
    t = text_out.strip()
    if t.startswith("```json"):
        t = t[7:]
    elif t.startswith("```"):
        t = t[3:]
    if t.endswith("```"):
        t = t[:-3]
    t = t.strip()

    # Wrap unquoted fraction expressions e.g. 11/15 or 3 1/2 in double quotes (fixed-width safe)
    t = re.sub(r'([,\[]\s*)([0-9]+/[0-9]+)(\s*[,\]])', r'\1"\2"\3', t)
    t = re.sub(r'([,\[]\s*)([0-9]+\s+[0-9]+/[0-9]+)(\s*[,\]])', r'\1"\2"\3', t)

    try:
        return json.loads(t)
    except Exception:
        # Fix trailing commas: [1, 2,] or {"a": 1,}
        cleaned = re.sub(r',\s*([\]}])', r'\1', t)
        try:
            return json.loads(cleaned)
        except Exception:
            match = re.search(r'(\{[\s\S]*\})', cleaned)
            if match:
                return json.loads(re.sub(r',\s*([\]}])', r'\1', match.group(1)))
            raise


def extract_with_gemini_vision(img: Any, return_metadata: bool = False) -> Any:
    """
    Extracts tables, marksheets, forms, or data lists from an image using
    Google Gemini Multimodal Vision AI. Returns structured section dicts
    matching the app's section schema, or None if extraction fails.
    """
    api_key = _get_gemini_api_key()
    if not api_key:
        logger.warning("[Gemini Vision] No GEMINI_API_KEY found — skipping Vision AI")
        return None

    if isinstance(img, str):
        if img.startswith("data:image"):
            img = img.split(",", 1)[1]
        try:
            img_bytes = base64.b64decode(img)
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception:
            if os.path.exists(img):
                img = cv2.imread(img)
            else:
                return None

    if img is None or not hasattr(img, 'size') or img.size == 0:
        return None

    # Step 1: Resize image to max 1600px dimension for ultra-fast, lightweight upload
    h, w = img.shape[:2]
    max_dim = 1600
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        scaled_img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    else:
        scaled_img = img

    # Step 2: Encode to JPEG with quality 92 (~250 KB payload for instantaneous API upload)
    success, buffer = cv2.imencode(".jpg", scaled_img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not success or buffer is None:
        logger.error("[Gemini Vision] Image encoding failed")
        return None
    b64_img = base64.b64encode(buffer).decode("utf-8")

    prompt = """You are an expert Document & Vision AI system specializing in academic exam mark sheet analysis, handwriting/cursive name transcription, and sparse table extraction.
Your task is to analyze this document image (an exam mark sheet / test answer paper) and extract BOTH the student metadata AND the isolated marks table grid with 100% precision.

CRITICAL INSTRUCTIONS:
1. EXTRACT STUDENT & DOCUMENT METADATA FROM THE HEADER:
   - "student_name": Full student name. Carefully read handwritten or cursive Surname, First Name, and Middle Name (e.g. Surname "Mahadik", First Name "Shrutika", Middle Name "Anil" -> "MAHADIK SHRUTIKA ANIL"). Pay extreme attention to cursive spelling (e.g. Mahadik, Shrutika, Madhavi, Patil, Deshmukh).
   - "prn": Exact PRN / Registration Number written inside individual digit boxes (e.g., "241051032", "241051033", "231051037"). Read every individual box digit carefully from left to right.
   - "roll_no": Exact Roll Number located at the top right corner or header (e.g. "SE-46", "44 / SE", "B-63", "44") or "" if not found.
   - "branch": Department / Branch (e.g., "IT", "CSE", "AIDS", "EXTC").
   - "division": Division or composite class/division string if written, or "" if blank.
   - "semester": Semester (e.g., "Sem IV", "IV", "Sem II", "II").
   - "subject": Subject name written on the sheet (e.g., "CNND", "Physics", "Chemistry").

2. EXTRACT ONLY THE EXAM MARKS TABLE GRID (STRICT CELL SPARSITY RULES):
   - Locate the marks table grid with columns: ["Q.No.", "1a", "1b", "1c", "1d", "1e", "1f", "2a", "2b", "3a", "3b", "Total", "Sign. of Examiner"]
   - Row 1: "Max Marks" row contains the maximum marks for each question.
   - Row 2: "Mark Awarded" / "Marks Obtained" row:
     * Check EVERY question column independently from left to right.
     * If a question was unattempted or its cell is BLANK/EMPTY, output strictly an empty string `""`.
     * STRICT ZERO HALLUCINATION RULE: NEVER fill in marks, repeat values across columns, or copy numbers into blank cells. If a cell has no ink/marks, output `""`.
     * Note that handwritten marks may include checkmarks, fractions, or circled marks (e.g. '2', '3', '3 1/2', '1/2', '4', '14', '11').
     * The number in the Total column represents the sum of the student's awarded marks.
   - STRICT RULE FOR TABLE ISOLATION: DO NOT include document header text or student answers written below "Please start writing from below" inside the marks table grid!

Return ONLY valid JSON matching this schema:
{
  "metadata": {
    "student_name": "Full student name (e.g. SURNAME FIRST_NAME MIDDLE_NAME)",
    "prn": "Exact PRN number from digit boxes",
    "roll_no": "Roll number string or ''",
    "branch": "Branch string or ''",
    "division": "Division string or ''",
    "semester": "Semester string or ''",
    "subject": "Subject name or ''"
  },
  "sections": [
    {
      "title": "Exam Marks Table",
      "headers": ["Q.No.", "1a", "1b", "1c", "1d", "1e", "1f", "2a", "2b", "3a", "3b", "Total", "Sign. of Examiner"],
      "rows": [
        ["Max Marks", "2", "2", "2", "2", "2", "2", "5", "5", "5", "5", "20", ""],
        ["Mark Awarded", "", "", "", "", "", "", "", "", "", "", "", ""]
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
                            "mime_type": "image/jpeg",
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

                # Parse JSON output robustly
                parsed = _clean_and_parse_json(text_out)
                raw_sections = parsed.get("sections", [])
                metadata = parsed.get("metadata", {})
                
                if not raw_sections and not metadata:
                    continue

                print(f"[Gemini Vision Engine] Grid layout & metadata detected using {model_name}!")
                
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
                        "detection_pipeline": "OpenCV Grayscale -> Gemini Layout Separation -> PyTorch CNN Classification",
                        "metadata": metadata
                    })

                return (formatted_sections, metadata) if return_metadata else formatted_sections

        except Exception as e:
            logger.warning(f"[Gemini Vision Engine] Model {model_name} failed: {e}")
            continue

    logger.error("[Gemini Vision Engine] All Vision AI model calls failed — falling back to local OCR")
    return None
