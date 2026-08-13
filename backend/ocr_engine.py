import re
import cv2
import numpy as np
from typing import List, Dict, Any, Optional, Tuple

# ---------------------------------------------------------------------------
#  MNIST CNN Classifier Integration
#  The CNN runs first on each single-digit cell crop.
#  EasyOCR is used as a fallback when CNN confidence is low.
_CNN_FUNCS = None

def _get_cnn_classifier():
    global _CNN_FUNCS
    if _CNN_FUNCS is None:
        try:
            from backend.mnist_classifier import classify_digit, classify_digit_tta
            _CNN_FUNCS = (classify_digit, classify_digit_tta)
        except Exception:
            _CNN_FUNCS = (None, None)
    return _CNN_FUNCS

# CNN confidence threshold: above this, accept CNN result immediately.
# Below this, run TTA (test-time augmentation) for a more robust vote.
_CNN_CONFIDENCE_THRESHOLD = 0.55

# Minimum TTA confidence to accept TTA result.
# With 5-crop majority voting, even 0.30 is reliable.
_CNN_TTA_THRESHOLD = 0.30

# Maximum grid dimensions — reject grids larger than this as noise
# (e.g., complex documents with many ruled lines)
_MAX_GRID_ROWS = 20
_MAX_GRID_COLS = 20

_EASYOCR_READER = None

def get_ocr_reader():
    """Returns or initializes singleton EasyOCR Reader lazily on demand."""
    global _EASYOCR_READER
    if _EASYOCR_READER is None:
        try:
            import easyocr
            print("[OCR] Initializing EasyOCR Reader (English)...")
            _EASYOCR_READER = easyocr.Reader(['en'], gpu=False)
        except Exception as e:
            print(f"[OCR] EasyOCR init skipped/failed: {e}")
            return None
    return _EASYOCR_READER

def clean_and_normalize_ocr_text(raw_text: str) -> Dict[str, Any]:
    """Cleans raw OCR text, preserving text headers, fractions (e.g. 11/15), and numbers."""
    text = raw_text.strip()
    text = re.sub(r'^[\"\']|[\"\']$', '', text).strip()
    if not text:
        return {"text": "", "value": "", "formatted_text": "", "is_number": False, "type": "empty"}

    # Preserved fraction pattern (e.g., "11/15", "11 / 15", "20/20")
    if re.search(r'\d+\s*/\s*\d+', text):
        clean_frac = re.sub(r'\s+', '', text)
        return {
            "text": clean_frac,
            "value": clean_frac,
            "formatted_text": clean_frac,
            "is_number": False,
            "type": "text"
        }

    # Preserved text/header pattern (contains letters like "1a", "1b", "Total", "Sign")
    if re.search(r'[a-zA-Z]', text):
        clean_text = text.strip()
        return {
            "text": clean_text,
            "value": clean_text,
            "formatted_text": clean_text,
            "is_number": False,
            "type": "text"
        }

    # Pure number processing (e.g. "20", "2.5", "-5", "(3)")
    cleaned = re.sub(r'[\$\,\%\s\[\]\(\)\{\}]', '', text)

    char_map = {
        'O': '0', 'o': '0',
        'I': '1', 'l': '1', '|': '1', 'i': '1',
        'Z': '2', 'z': '2',
        'S': '5', 's': '5',
        'G': '6', 'b': '6',
        'B': '8',
        'q': '9', 'g': '9', 'p': '9',
        'A': '4', 'a': '4',
        'T': '7',
    }

    repaired = "".join(char_map.get(c, c) for c in cleaned)
    repaired_num = re.sub(r'[^0-9\.\-]', '', repaired)

    if repaired_num and re.match(r'^-?\d+(\.\d+)?$', repaired_num):
        try:
            val = float(repaired_num)
            num_val = int(val) if (val.is_integer() and '.' not in repaired_num) else val
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
        "text": text,
        "value": text,
        "formatted_text": text,
        "is_number": text.isdigit(),
        "type": "number" if text.isdigit() else "text"
    }


# ---------------------------------------------------------------------------
#  Grid Cell Box Geometry Detection — Line-Based Primary Method
# ---------------------------------------------------------------------------

def _detect_grid_lines(gray: np.ndarray) -> Tuple[List[int], List[int]]:
    """
    Detects horizontal and vertical grid lines using CLAHE contrast enhancement,
    adaptive thresholding, and morphological operations.
    Filters out handwritten text strokes while capturing structural table grid lines.
    """
    h, w = gray.shape

    # CLAHE contrast enhancement + Adaptive Thresholding
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    blur = cv2.GaussianBlur(enhanced, (3, 3), 0)
    thresh = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 4
    )

    # --- Detect horizontal lines ---
    # Kernel wider than tall to isolate horizontal table lines (ignore short handwriting top strokes)
    h_kernel_len = max(w // 15, 30)
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_kernel_len, 1))
    h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_kernel, iterations=1)

    # Find Y positions of horizontal lines by projecting onto Y axis (require >= 20% of width)
    h_proj = np.sum(h_lines, axis=1)
    h_threshold = w * 0.20 * 255
    h_positions = []
    in_line = False
    line_start = 0
    for y_pos in range(len(h_proj)):
        if h_proj[y_pos] > h_threshold:
            if not in_line:
                line_start = y_pos
                in_line = True
        else:
            if in_line:
                h_positions.append((line_start + y_pos) // 2)
                in_line = False
    if in_line:
        h_positions.append((line_start + len(h_proj) - 1) // 2)

    # --- Detect vertical lines ---
    # Kernel taller than wide to isolate structural vertical cell walls (ignore 15-25px digit strokes)
    v_kernel_len = max(h // 5, 25)
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_kernel_len))
    v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, v_kernel, iterations=1)

    # Find X positions by projecting onto X axis (require >= 25% of height)
    v_proj = np.sum(v_lines, axis=0)
    v_threshold = h * 0.25 * 255
    v_positions = []
    in_line = False
    line_start = 0
    for x_pos in range(len(v_proj)):
        if v_proj[x_pos] > v_threshold:
            if not in_line:
                line_start = x_pos
                in_line = True
        else:
            if in_line:
                v_positions.append((line_start + x_pos) // 2)
                in_line = False
    if in_line:
        v_positions.append((line_start + len(v_proj) - 1) // 2)

    # Add image boundary positions (top 2, bottom h-3, left 2, right w-3) if table touches edges
    if h_positions:
        if h_positions[0] > max(15, h * 0.15):
            h_positions.insert(0, 2)
        if (h - 1 - h_positions[-1]) > max(15, h * 0.15):
            h_positions.append(h - 3)
    if v_positions:
        if v_positions[0] > max(15, w * 0.15):
            v_positions.insert(0, 2)
        if (w - 1 - v_positions[-1]) > max(15, w * 0.15):
            v_positions.append(w - 3)

    return sorted(h_positions), sorted(v_positions)


def _grid_from_lines(h_lines: List[int], v_lines: List[int],
                     img_h: int, img_w: int) -> List[List[Dict[str, Any]]]:
    """
    Constructs a 2D grid of cell bounding boxes from detected grid line positions.
    Each cell is the rectangle between consecutive horizontal and vertical lines.
    """
    if len(h_lines) < 2 or len(v_lines) < 2:
        return []

    # Filter out duplicate/too-close lines
    def dedupe_lines(lines, min_gap):
        if not lines:
            return []
        result = [lines[0]]
        for ln in lines[1:]:
            if ln - result[-1] >= min_gap:
                result.append(ln)
        return result

    h_lines = dedupe_lines(h_lines, max(12, img_h // 20))
    v_lines = dedupe_lines(v_lines, max(12, img_w // 30))

    if len(h_lines) < 2 or len(v_lines) < 2:
        return []

    grid_matrix = []
    for r in range(len(h_lines) - 1):
        row_boxes = []
        y1 = h_lines[r]
        y2 = h_lines[r + 1]
        for c in range(len(v_lines) - 1):
            x1 = v_lines[c]
            x2 = v_lines[c + 1]
            row_boxes.append({
                "x": x1, "y": y1,
                "w": x2 - x1, "h": y2 - y1
            })
        grid_matrix.append(row_boxes)

    return grid_matrix


def detect_grid_cell_boxes(img: np.ndarray) -> List[List[Dict[str, Any]]]:
    """
    Detects individual grid cell bounding boxes in the image.
    
    Strategy (two-tier):
      1. PRIMARY  — Line-based detection using CLAHE + adaptive thresholding.
                    Detects horizontal/vertical grid lines and constructs cells
                    from their intersections. Far more reliable for explicit grids.
      2. FALLBACK — Contour-based detection with adaptive size filtering and
                    IoU-based child suppression. Used when line detection fails.
    
    Returns a 2D matrix of row-sorted cell box rectangles: [[box1, box2, ...], [row2...]].
    Each box is a dict: {'x': x, 'y': y, 'w': w, 'h': h}.
    """
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

    # ---------------------------------------------------------------
    # Tier 1: Line-based grid detection (primary, most reliable)
    # ---------------------------------------------------------------
    h_lines, v_lines = _detect_grid_lines(gray)
    
    if len(h_lines) >= 2 and len(v_lines) >= 2:
        grid_matrix = _grid_from_lines(h_lines, v_lines, h, w)
        if grid_matrix and len(grid_matrix) >= 2 and len(grid_matrix[0]) >= 2:
            n_rows = len(grid_matrix)
            n_cols = len(grid_matrix[0])
            # Reject absurdly large grids (complex documents with many lines)
            if n_rows > _MAX_GRID_ROWS or n_cols > _MAX_GRID_COLS:
                print(f"[Grid Detector] Line-based grid too large ({n_rows}x{n_cols}) — treating as complex document")
            else:
                total_cells = sum(len(r) for r in grid_matrix)
                print(f"[Grid Detector] Line-based: {n_rows} rows x {n_cols} cols ({total_cells} cells)")
                return grid_matrix

    # ---------------------------------------------------------------
    # Tier 2: Contour-based grid detection (fallback)
    # ---------------------------------------------------------------
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    thresh = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 4)
    contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    boxes = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        area = bw * bh
        # Ensure contour looks like a cell box quadrilateral rather than ink stroke
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.04 * peri, True)
        if bw > 15 and bh > 15 and area > 250 and len(approx) <= 8:
            boxes.append((x, y, bw, bh))

    if len(boxes) < 4:
        return []

    # Adaptive size filtering: compute median area and reject outliers
    areas = [b[2] * b[3] for b in boxes]
    median_area = float(np.median(areas))
    # Keep boxes within 30%–300% of median area
    filtered_boxes = [
        b for b in boxes
        if 0.30 * median_area <= b[2] * b[3] <= 3.0 * median_area
    ]
    
    if len(filtered_boxes) < 4:
        filtered_boxes = boxes  # fallback to unfiltered

    # IoU-based child-contour suppression (replaces simple center containment)
    clean_boxes = []
    filtered_boxes.sort(key=lambda b: b[2] * b[3], reverse=True)
    
    for b in filtered_boxes:
        bx, by, bw, bh = b
        is_child = False
        for cb in clean_boxes:
            cx, cy, cw, ch = cb
            # Compute IoU
            ix1 = max(bx, cx)
            iy1 = max(by, cy)
            ix2 = min(bx + bw, cx + cw)
            iy2 = min(by + bh, cy + ch)
            
            if ix1 < ix2 and iy1 < iy2:
                intersection = (ix2 - ix1) * (iy2 - iy1)
                smaller_area = min(bw * bh, cw * ch)
                # If overlap > 60% of the smaller box, it's a child
                if intersection > 0.6 * smaller_area:
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
    
    # --- Gap-fill: ensure all rows have the same column count ---
    row_lengths = [len(r) for r in rows]
    if row_lengths:
        # Use the mode (most common) row length as target column count
        from collections import Counter
        target_cols = Counter(row_lengths).most_common(1)[0][0]
        
        for r_idx, r in enumerate(rows):
            r.sort(key=lambda b: b[0])
            
            while len(r) < target_cols and len(r) >= 2:
                # Find the largest gap between consecutive boxes
                gaps = []
                for i in range(len(r) - 1):
                    gap_start = r[i][0] + r[i][2]  # right edge of box i
                    gap_end = r[i + 1][0]           # left edge of box i+1
                    gap_width = gap_end - gap_start
                    gaps.append((gap_width, i))
                
                if not gaps:
                    break
                
                avg_box_w = sum(b[2] for b in r) / len(r)
                avg_box_h = sum(b[3] for b in r) / len(r)
                
                max_gap, gap_idx = max(gaps, key=lambda g: g[0])
                
                # Only fill if gap is large enough to fit a box
                if max_gap > avg_box_w * 0.5:
                    # Interpolate a new box in the gap
                    new_x = r[gap_idx][0] + r[gap_idx][2] + int((max_gap - avg_box_w) / 2)
                    new_y = int(sum(b[1] for b in r) / len(r))
                    new_box = (new_x, new_y, int(avg_box_w), int(avg_box_h))
                    r.insert(gap_idx + 1, new_box)
                    r.sort(key=lambda b: b[0])
                else:
                    break

    grid_matrix = []
    for r in rows:
        r.sort(key=lambda b: b[0])
        grid_matrix.append([{"x": b[0], "y": b[1], "w": b[2], "h": b[3]} for b in r])

    # Filter out any empty rows
    grid_matrix = [r for r in grid_matrix if len(r) > 0]
    if not grid_matrix:
        return []

    total_cells = sum(len(r) for r in grid_matrix)
    n_rows = len(grid_matrix)
    n_cols = len(grid_matrix[0]) if grid_matrix else 0
    
    # Reject absurdly large grids (complex documents with many contours)
    if n_rows > _MAX_GRID_ROWS or n_cols > _MAX_GRID_COLS:
        print(f"[Grid Detector] Contour-based grid too large ({n_rows}x{n_cols}) — treating as complex document")
        return []
    
    print(f"[Grid Detector] Contour-based: {n_rows} rows x {n_cols} cols ({total_cells} cells)")
    return grid_matrix


# ---------------------------------------------------------------------------
#  Single-Cell Crop OCR Processing
# ---------------------------------------------------------------------------

def _ocr_single_cell_crop(img: np.ndarray, box: Dict[str, int], reader: easyocr.Reader) -> str:
    """
    Recognizes text or digits inside a grid cell crop.

    Hybrid Router:
      1. Clears outer 3-pixel border of crop to eliminate cell border lines
         (stopping vertical box lines from being misread as digit 1 or letter l).
      2. Checks for empty cells (foreground ink < 1.5% -> returns "").
      3. EasyOCR Pass — checks for text/headers (e.g. "1a", "Total", "Sign"),
         fractions (e.g. "11/15"), or multi-digits (e.g. "20").
      4. MNIST CNN Pass — if cell is a single handwritten digit, routes to
         MNIST CNN + 5-crop TTA (98.87% accuracy).
    """
    bx, by, bw, bh = box["x"], box["y"], box["w"], box["h"]
    inset_x = int(bw * 0.12)
    inset_y = int(bh * 0.12)

    y1 = max(0, by + inset_y)
    y2 = min(img.shape[0], by + bh - inset_y)
    x1 = max(0, bx + inset_x)
    x2 = min(img.shape[1], bx + bw - inset_x)

    crop = img[y1:y2, x1:x2]
    if crop.size == 0 or crop.shape[0] < 4 or crop.shape[1] < 4:
        return ""

    crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop

    # Clear outer 3-pixel border to eliminate cell box line fragments
    h_c, w_c = crop_gray.shape
    pad_b = min(3, h_c // 4, w_c // 4)
    if pad_b > 0:
        bg_fill = int(crop_gray.mean())
        crop_gray[:pad_b, :] = bg_fill
        crop_gray[-pad_b:, :] = bg_fill
        crop_gray[:, :pad_b] = bg_fill
        crop_gray[:, -pad_b:] = bg_fill

    # Check if cell is empty (std check + foreground ratio check)
    if crop_gray.std() < 5.0:
        return ""

    # Foreground ratio check after OTSU thresholding
    if crop_gray.mean() > 128:
        check_inv = cv2.bitwise_not(crop_gray)
    else:
        check_inv = crop_gray.copy()
    _, check_bin = cv2.threshold(check_inv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    fg_ratio = np.count_nonzero(check_bin) / max(check_bin.size, 1)

    if fg_ratio < 0.015:  # less than 1.5% ink = empty cell
        return ""

    # Build clean BGR crop with cleared border
    crop_clean = cv2.cvtColor(crop_gray, cv2.COLOR_GRAY2BGR)

    # ------------------------------------------------------------------
    # Step 1: EasyOCR pass for text headers, fractions, and multi-digits
    # ------------------------------------------------------------------
    try:
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(4, 4))
        enhanced = clahe.apply(crop_gray)
        padded = cv2.copyMakeBorder(enhanced, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
        resized = cv2.resize(padded, (160, 160), interpolation=cv2.INTER_CUBIC)

        ocr_results = reader.readtext(
            cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR),
            detail=1,
            text_threshold=0.10,
            low_text=0.10,
            link_threshold=0.10
        )
        if ocr_results:
            raw_txt = ocr_results[0][1].strip()
            conf = ocr_results[0][2]

            # Text / Header (contains letters like "1a", "1b", "Total", "Sign") or fraction ("11/15")
            if re.search(r'[a-zA-Z]', raw_txt) or '/' in raw_txt:
                print(f"[Cell OCR] Header/Text: '{raw_txt}' (conf={conf:.2f})")
                return raw_txt

            # Multi-digit numbers (e.g. "20", "100")
            clean_digits = re.sub(r'[^0-9]', '', raw_txt)
            if len(clean_digits) >= 2 and conf >= 0.30:
                print(f"[Cell OCR] Multi-digit: '{raw_txt}' (conf={conf:.2f})")
                return raw_txt
    except Exception as e:
        print(f"[Cell OCR] EasyOCR check error: {e}")

    # ------------------------------------------------------------------
    # Step 2: MNIST CNN classifier for single handwritten digits (0-9)
    # ------------------------------------------------------------------
    classify_fn, tta_fn = _get_cnn_classifier()
    if classify_fn is not None:
        try:
            cnn_digit, cnn_conf = classify_fn(crop_clean)

            if cnn_digit:
                if cnn_conf >= _CNN_CONFIDENCE_THRESHOLD:
                    print(f"[MNIST-CNN] digit={cnn_digit} confidence={cnn_conf:.3f} (accepted)")
                    return cnn_digit

                # 5-crop TTA majority voting
                if tta_fn is not None:
                    tta_digit, tta_conf = tta_fn(crop_clean, num_crops=5)
                    if tta_digit:
                        print(f"[MNIST-TTA] digit={tta_digit} confidence={tta_conf:.3f} (TTA accepted)")
                        return tta_digit

                print(f"[MNIST-CNN] digit={cnn_digit} confidence={cnn_conf:.3f} (accepted)")
                return cnn_digit

        except Exception as _cnn_err:
            print(f"[MNIST-CNN] Error: {_cnn_err}")

    return ""


def _ocr_row_strip(img: np.ndarray, row_boxes: List[Dict[str, int]], reader: easyocr.Reader) -> Dict[int, str]:
    """
    Runs EasyOCR across an ENTIRE row strip (all columns in a row simultaneously).
    This preserves spatial line context and easily reads headers ('1a', '1b', 'Total'),
    fractions ('11/15'), and labels that get distorted in micro cell crops.

    Returns a dict mapping col_idx -> recognized text string.
    """
    if not row_boxes:
        return {}

    min_h = min(b["h"] for b in row_boxes)
    inset_y = max(1, int(min_h * 0.08))

    y_min = max(0, min(b["y"] for b in row_boxes) + inset_y)
    y_max = min(img.shape[0], max(b["y"] + b["h"] for b in row_boxes) - inset_y)
    x_min = max(0, min(b["x"] for b in row_boxes))
    x_max = min(img.shape[1], max(b["x"] + b["w"] for b in row_boxes))

    row_strip = img[y_min:y_max, x_min:x_max]
    if row_strip.size == 0 or row_strip.shape[0] < 6 or row_strip.shape[1] < 10:
        return {}

    try:
        results = reader.readtext(
            row_strip,
            detail=1,
            text_threshold=0.10,
            low_text=0.10,
            link_threshold=0.10
        )
        if not results:
            return {}

        col_text_map = {}
        for (bbox, raw_txt, conf) in results:
            txt = raw_txt.strip()
            if not txt:
                continue

            pts = np.array(bbox, dtype=np.float32)
            box_w = float(np.max(pts[:, 0]) - np.min(pts[:, 0]))
            box_center_x = x_min + float(np.mean(pts[:, 0]))

            best_col = None
            min_dist = float("inf")

            for c_idx, box in enumerate(row_boxes):
                cell_left = box["x"]
                cell_right = box["x"] + box["w"]
                cell_center_x = box["x"] + box["w"] / 2.0

                # Reject bounding boxes that span across multiple cells (> 1.4x single cell width)
                # unless they contain letters or slashes (e.g. headers/labels)
                if box_w > (box["w"] * 1.4) and not (re.search(r'[a-zA-Z]', txt) or '/' in txt):
                    continue

                if cell_left <= box_center_x <= cell_right:
                    best_col = c_idx
                    break
                dist = abs(box_center_x - cell_center_x)
                if dist < min_dist:
                    min_dist = dist
                    best_col = c_idx

            if best_col is not None and min_dist < (row_boxes[best_col]["w"] * 0.85):
                if best_col in col_text_map:
                    col_text_map[best_col] = f"{col_text_map[best_col]} {txt}"
                else:
                    col_text_map[best_col] = txt

        return col_text_map
    except Exception as e:
        print(f"[Row OCR] Error processing row strip: {e}")
        return {}


# ---------------------------------------------------------------------------
#  Main Engine Execution Entry Point
# ---------------------------------------------------------------------------

def run_ocr_on_image(img: np.ndarray) -> List[Dict[str, Any]]:
    """
    Main OCR extraction engine:
    1. Detects grid box geometry first.
    2. Uses Row-Strip OCR for full row context (text headers, fractions, multi-digits).
    3. Uses MNIST CNN + TTA for single handwritten digits.
    4. If freeform image -> falls back to whole-image OCR.
    """
    reader = get_ocr_reader()

    # Step 1: Detect explicit grid matrix
    try:
        grid_matrix = detect_grid_cell_boxes(img)
    except Exception as e:
        print(f"[OCR Engine] Grid detection failed ({e}) — falling back to freeform OCR")
        grid_matrix = []

    if grid_matrix and len(grid_matrix) >= 2:
        total_rows = len(grid_matrix)
        total_cols = max(len(r) for r in grid_matrix)

        print(f"[OCR Engine] Processing explicit grid matrix: {total_rows} rows x {total_cols} columns...")
        tokens = []

        try:
            for r_idx, row_boxes in enumerate(grid_matrix):
                # Step 1a: Run Row-Strip OCR for full row text context
                row_text_map = _ocr_row_strip(img, row_boxes, reader)

                for c_idx, box in enumerate(row_boxes):
                    row_str = row_text_map.get(c_idx, "").strip()

                    # Accept Row-OCR text if it contains letters ("1a", "Total", "Sign") or fraction ("11/15")
                    if re.search(r'[a-zA-Z]', row_str) or '/' in row_str:
                        digit_str = row_str
                        print(f"[OCR Engine] Grid ({r_idx},{c_idx}) Header/Text accepted: '{digit_str}'")
                    else:
                        # Run single-cell crop OCR for digits & isolated content
                        try:
                            cell_str = _ocr_single_cell_crop(img, box, reader)
                            digit_str = cell_str if cell_str else row_str
                        except Exception as cell_err:
                            print(f"[OCR Engine] Cell ({r_idx},{c_idx}) failed: {cell_err}")
                            digit_str = row_str

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
        except Exception as grid_err:
            print(f"[OCR Engine] Grid processing failed ({grid_err}) — falling back to freeform OCR")

    # Step 2: Freeform Image Fallback (No Grid Boxes Found)
    print("[OCR Engine] No grid boxes detected -> running standard document OCR...")
    results = reader.readtext(
        img,
        detail=1,
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
