import re
import cv2
import numpy as np
import easyocr
from typing import List, Dict, Any, Optional

# ---------------------------------------------------------------------------
#  MNIST CNN Classifier Integration
#  The CNN runs first on each single-digit cell crop.
#  EasyOCR is used as a fallback when CNN confidence is low.
# ---------------------------------------------------------------------------
try:
    from backend.mnist_classifier import classify_digit as _cnn_classify
    _CNN_AVAILABLE = True
except ImportError:
    _cnn_classify = None
    _CNN_AVAILABLE = False

# Minimum CNN softmax confidence to trust CNN result over EasyOCR fallback
_CNN_CONFIDENCE_THRESHOLD = 0.70

_EASYOCR_READER: Optional[easyocr.Reader] = None

def get_ocr_reader() -> easyocr.Reader:
    """Returns or initializes singleton EasyOCR Reader."""
    global _EASYOCR_READER
    if _EASYOCR_READER is None:
        print("[OCR] Initializing EasyOCR Reader (English)...")
        _EASYOCR_READER = easyocr.Reader(['en'], gpu=False)
    return _EASYOCR_READER

def clean_and_normalize_ocr_text(raw_text: str) -> Dict[str, Any]:
    """Cleans raw OCR text and repairs common handwritten digit misreads."""
    text = raw_text.strip()
    if not text:
        return {"text": "", "value": "", "formatted_text": "", "is_number": False, "type": "empty"}

    cleaned = re.sub(r'[\$\,\%\s\[\]\(\)\{\}]', '', text)

    char_map = {
        'O': '0', 'o': '0', 'D': '0', 'Q': '0',
        'I': '1', 'l': '1', '|': '1', 'i': '1', '/': '1', '\\': '1', '!': '1',
        'Z': '2', 'z': '2',
        'S': '5', 's': '5',
        'G': '6', 'b': '6',
        'B': '8',
        'q': '9', 'g': '9', 'P': '9', 'p': '8', 'h': '7',
        'A': '4', 'a': '4',
    }

    repaired = "".join(char_map.get(c, c) for c in cleaned)
    repaired = re.sub(r'[^0-9\.\-]', '', repaired)

    if repaired and re.match(r'^-?\d+(\.\d+)?$', repaired):
        try:
            val = float(repaired)
            num_val = int(val) if (val.is_integer() and '.' not in repaired) else val
            return {
                "text": str(num_val),
                "value": num_val,
                "formatted_text": str(num_val),
                "is_number": True,
                "type": "number"
            }
        except ValueError:
            pass

    return {
        "text": repaired or text,
        "value": repaired or text,
        "formatted_text": repaired or text,
        "is_number": repaired.isdigit() if repaired else False,
        "type": "number" if (repaired and repaired.isdigit()) else "text"
    }


# ---------------------------------------------------------------------------
#  Grid Cell Box Geometry Detection
# ---------------------------------------------------------------------------

def detect_grid_cell_boxes(img: np.ndarray) -> List[List[Dict[str, Any]]]:
    """
    Detects individual grid cell bounding boxes in the image using contour analysis.
    Returns a 2D matrix of row-sorted cell box rectangles: [[box1, box2, ...], [row2...]].
    Each box is a dict: {'x': x, 'y': y, 'w': w, 'h': h}.
    """
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    boxes = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        area = bw * bh
        if 18 < bw < (w / 4) and 18 < bh < (h / 2) and area > 350:
            boxes.append((x, y, bw, bh))

    if len(boxes) < 4:
        return []

    # Sort boxes by area descending to clean up child/sub-contours
    clean_boxes = []
    boxes.sort(key=lambda b: b[2] * b[3], reverse=True)
    for b in boxes:
        bx, by, bw, bh = b
        bcx, bcy = bx + bw / 2.0, by + bh / 2.0
        is_child = False
        for cb in clean_boxes:
            cx, cy, cw, ch = cb
            if cx <= bcx <= cx + cw and cy <= bcy <= cy + ch:
                is_child = True
                break
        if not is_child:
            clean_boxes.append(b)

    if len(clean_boxes) < 4:
        return []

    # Sort boxes top-to-bottom
    clean_boxes.sort(key=lambda b: b[1])

    # Group into rows by Y coordinate
    rows = []
    for b in clean_boxes:
        bx, by, bw, bh = b
        bcy = by + bh / 2.0
        matched_row = False
        for row in rows:
            avg_y = sum(item[1] + item[3]/2.0 for item in row) / len(row)
            if abs(bcy - avg_y) < (bh * 0.55):
                row.append(b)
                matched_row = True
                break
        if not matched_row:
            rows.append([b])

    # Sort rows top-to-bottom, cells in each row left-to-right
    rows.sort(key=lambda r: sum(b[1] for b in r) / len(r))
    grid_matrix = []
    for r in rows:
        r.sort(key=lambda b: b[0])
        grid_matrix.append([{"x": b[0], "y": b[1], "w": b[2], "h": b[3]} for b in r])

    # Filter out any empty rows
    grid_matrix = [r for r in grid_matrix if len(r) > 0]
    if not grid_matrix:
        return []

    print(f"[Grid Detector] Found grid geometry: {len(grid_matrix)} rows x {len(grid_matrix[0])} columns ({len(clean_boxes)} total boxes)")
    return grid_matrix


# ---------------------------------------------------------------------------
#  Single-Cell Crop OCR Processing
# ---------------------------------------------------------------------------

def _ocr_single_cell_crop(img: np.ndarray, box: Dict[str, int], reader: easyocr.Reader) -> str:
    """
    Recognizes a single handwritten digit inside a grid cell crop.

    Strategy (two-tier):
      1. PRIMARY  — MNIST-trained CNN (fast, ~99% accuracy on clean digits)
                    Used when confidence >= _CNN_CONFIDENCE_THRESHOLD (0.70)
      2. FALLBACK — EasyOCR with CLAHE/OTSU preprocessing
                    Used when CNN is uncertain or returns empty
    """
    bx, by, bw, bh = box["x"], box["y"], box["w"], box["h"]
    inset_x = int(bw * 0.14)
    inset_y = int(bh * 0.14)

    y1 = max(0, by + inset_y)
    y2 = min(img.shape[0], by + bh - inset_y)
    x1 = max(0, bx + inset_x)
    x2 = min(img.shape[1], bx + bw - inset_x)

    crop = img[y1:y2, x1:x2]
    if crop.size == 0 or crop.shape[0] < 4 or crop.shape[1] < 4:
        return ""

    # ------------------------------------------------------------------
    # Tier 1: MNIST CNN classifier
    # ------------------------------------------------------------------
    if _CNN_AVAILABLE and _cnn_classify is not None:
        try:
            cnn_digit, cnn_conf = _cnn_classify(crop)
            if cnn_digit and cnn_conf >= _CNN_CONFIDENCE_THRESHOLD:
                print(f"[MNIST-CNN] digit={cnn_digit} confidence={cnn_conf:.3f} (accepted)")
                return cnn_digit
            elif cnn_digit:
                print(f"[MNIST-CNN] digit={cnn_digit} confidence={cnn_conf:.3f} (low — falling back to EasyOCR)")
        except Exception as _cnn_err:
            print(f"[MNIST-CNN] Error: {_cnn_err} — falling back to EasyOCR")

    # ------------------------------------------------------------------
    # Tier 2: EasyOCR fallback pipeline
    # ------------------------------------------------------------------
    crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop

    # Step 2a: CLAHE contrast boost
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(4, 4))
    enhanced = clahe.apply(crop_gray)

    padded = cv2.copyMakeBorder(enhanced, 25, 25, 25, 25, cv2.BORDER_CONSTANT, value=255)
    resized = cv2.resize(padded, (140, 140), interpolation=cv2.INTER_CUBIC)

    results = reader.readtext(
        cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR),
        allowlist='0123456789',
        detail=0,
        text_threshold=0.04,
        low_text=0.04,
        link_threshold=0.04,
        contrast_ths=0.01
    )

    if results and results[0].strip():
        return results[0].strip()[0]

    # Step 2b: OTSU binarized fallback for thin/faint strokes
    _, crop_bin = cv2.threshold(crop_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bin_padded = cv2.copyMakeBorder(crop_bin, 25, 25, 25, 25, cv2.BORDER_CONSTANT, value=255)
    bin_resized = cv2.resize(bin_padded, (140, 140), interpolation=cv2.INTER_CUBIC)

    res_bin = reader.readtext(
        cv2.cvtColor(bin_resized, cv2.COLOR_GRAY2BGR),
        allowlist='0123456789',
        detail=0,
        text_threshold=0.02,
        low_text=0.02
    )

    if res_bin and res_bin[0].strip():
        return res_bin[0].strip()[0]

    return ""


# ---------------------------------------------------------------------------
#  Main Engine Execution Entry Point
# ---------------------------------------------------------------------------

def run_ocr_on_image(img: np.ndarray) -> List[Dict[str, Any]]:
    """
    Main OCR extraction engine:
    1. Detects grid box geometry first.
    2. If grid detected -> extracts numbers into explicit (row_i, col_j) grid cells.
    3. If freeform image -> falls back to whole-image OCR.
    """
    reader = get_ocr_reader()

    # Step 1: Detect explicit grid matrix
    grid_matrix = detect_grid_cell_boxes(img)

    if grid_matrix and len(grid_matrix) >= 2:
        total_rows = len(grid_matrix)
        total_cols = max(len(r) for r in grid_matrix)

        print(f"[OCR Engine] Processing explicit grid matrix: {total_rows} rows x {total_cols} columns...")
        tokens = []

        for r_idx, row_boxes in enumerate(grid_matrix):
            for c_idx, box in enumerate(row_boxes):
                digit_str = _ocr_single_cell_crop(img, box, reader)
                normalized = clean_and_normalize_ocr_text(digit_str)

                tokens.append({
                    "id": f"grid_cell_{r_idx}_{c_idx}",
                    "raw_text": digit_str,
                    "text": normalized["text"],
                    "value": normalized["value"],
                    "formatted_text": normalized["formatted_text"],
                    "is_number": normalized["is_number"],
                    "type": normalized["type"],
                    "confidence": 0.95 if normalized["text"] else 0.0,
                    "bbox": [box["x"], box["y"], box["w"], box["h"]],
                    "center": [box["x"] + box["w"] / 2.0, box["y"] + box["h"] / 2.0],
                    "grid_row": r_idx,
                    "grid_col": c_idx,
                    "grid_total_rows": total_rows,
                    "grid_total_cols": total_cols
                })

        print(f"[OCR Engine] Grid extraction finished: {sum(1 for t in tokens if t['text'])} filled cells out of {len(tokens)} total.")
        return tokens

    # Step 2: Freeform Image Fallback (No Grid Boxes Found)
    print("[OCR Engine] No grid boxes detected -> running standard document OCR...")
    results = reader.readtext(
        img,
        detail=1,
        allowlist='0123456789.-',
        text_threshold=0.15,
        low_text=0.15,
        link_threshold=0.15,
        mag_ratio=2.0,
        slope_ths=0.5,
        width_ths=0.7,
        contrast_ths=0.05,
    )

    tokens = []
    for idx, (bbox, raw_text, confidence) in enumerate(results):
        if not raw_text or not raw_text.strip():
            continue

        pts = np.array(bbox, dtype=np.int32)
        x_min = int(np.min(pts[:, 0]))
        y_min = int(np.min(pts[:, 1]))
        x_max = int(np.max(pts[:, 0]))
        y_max = int(np.max(pts[:, 1]))
        w = max(1, x_max - x_min)
        h = max(1, y_max - y_min)

        normalized = clean_and_normalize_ocr_text(raw_text)
        tokens.append({
            "id": f"token_{idx}",
            "raw_text": raw_text,
            "text": normalized["text"],
            "value": normalized["value"],
            "formatted_text": normalized["formatted_text"],
            "is_number": normalized["is_number"],
            "type": normalized["type"],
            "confidence": float(confidence),
            "bbox": [x_min, y_min, w, h],
            "center": [x_min + w / 2.0, y_min + h / 2.0]
        })

    return tokens
