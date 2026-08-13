import numpy as np
from typing import List, Dict, Any

def detect_sections_and_tables(ocr_items: List[Dict[str, Any]], img_shape: tuple) -> List[Dict[str, Any]]:
    """
    Identifies document structure, section headers, and extracts sub-tables/matrices.
    If OCR tokens already contain explicit grid_row and grid_col coordinates,
    builds the table matrix directly with 100% precision.
    """
    if not ocr_items:
        return []

    # Check if tokens are explicitly assigned to grid cells (Grid Mode)
    grid_tokens = [t for t in ocr_items if "grid_row" in t and "grid_col" in t]

    if grid_tokens and len(grid_tokens) > 0:
        total_rows = max(t["grid_total_rows"] for t in grid_tokens)
        total_cols = max(t["grid_total_cols"] for t in grid_tokens)

        headers = [f"Column {c+1}" for c in range(total_cols)]
        grid_matrix = []

        for r_idx in range(total_rows):
            row_cells = [{"text": "", "value": "", "is_number": False, "bbox": None, "confidence": 0} for _ in range(total_cols)]
            grid_matrix.append(row_cells)

        for t in grid_tokens:
            r = t["grid_row"]
            c = t["grid_col"]
            if 0 <= r < total_rows and 0 <= c < total_cols:
                grid_matrix[r][c] = {
                    "text": t["text"],
                    "value": t["value"],
                    "is_number": t["is_number"] or t["text"].isdigit(),
                    "bbox": t["bbox"],
                    "confidence": t.get("confidence", 0.95)
                }

        # Check if Row 0 contains text headers (e.g. "1a", "1b", "Total", "Sign")
        import re
        row0_texts = [cell["text"] for cell in grid_matrix[0] if cell["text"]]
        has_text_headers = any(re.search(r'[a-zA-Z]', txt) for txt in row0_texts)

        if has_text_headers and len(row0_texts) >= max(2, int(total_cols * 0.15)):
            headers = [grid_matrix[0][c]["text"] or f"Column {c+1}" for c in range(total_cols)]
            grid_matrix = grid_matrix[1:]  # remove header row from data
            total_rows = len(grid_matrix)
            print(f"[Section Detector] Promoted Row 0 to table headers: {headers}")
        else:
            headers = [f"Column {c+1}" for c in range(total_cols)]

        print(f"[Section Detector] Created explicit grid section: {total_rows} rows x {total_cols} columns")

        return [{
            "section_id": "sec_1",
            "title": "SECTION 1",
            "bbox": [0, 0, img_shape[1], img_shape[0]],
            "headers": headers,
            "rows": grid_matrix,
            "rows_count": total_rows,
            "columns_count": total_cols
        }]

    # Freeform Document Mode: Group by Y center and cluster into columns
    # Filter to only non-grid tokens for freeform processing
    freeform_tokens = [t for t in ocr_items if "grid_row" not in t]
    if not freeform_tokens:
        freeform_tokens = ocr_items  # fallback to all if no distinction
    sorted_tokens = sorted(freeform_tokens, key=lambda t: (t["center"][1], t["center"][0]))

    rows = []
    current_row = [sorted_tokens[0]]

    for t in sorted_tokens[1:]:
        row_heights = [item["bbox"][3] for item in current_row]
        avg_height = sum(row_heights) / len(row_heights)
        row_y_center = sum(item["center"][1] for item in current_row) / len(current_row)

        if abs(t["center"][1] - row_y_center) <= (avg_height * 0.65):
            current_row.append(t)
        else:
            current_row.sort(key=lambda item: item["center"][0])
            rows.append(current_row)
            current_row = [t]

    if current_row:
        current_row.sort(key=lambda item: item["center"][0])
        rows.append(current_row)

    if not rows:
        return []

    # Check for Marks Table Header row to isolate the table from top document headers & bottom handwritten answers
    import re
    marks_header_idx = -1
    marks_footer_idx = len(rows)

    for r_idx, r in enumerate(rows):
        row_text_joined = " ".join([t["text"].lower() for t in r])
        # Look for table header keywords
        if any(kw in row_text_joined for kw in ["q.no", "q. no", "1a", "1b", "1c", "2a", "2b", "total", "sign"]):
            marks_header_idx = r_idx
            break

    for r_idx, r in enumerate(rows):
        row_text_joined = " ".join([t["text"].lower() for t in r])
        if "please start writing" in row_text_joined or "writing from below" in row_text_joined:
            marks_footer_idx = r_idx
            break

    if marks_header_idx != -1:
        # Keep only the rows corresponding to the Marks Table Grid
        filtered_rows = rows[marks_header_idx:marks_footer_idx]
        if filtered_rows:
            rows = filtered_rows
            print(f"[Section Detector] Isolated Marks Table: {len(rows)} table rows extracted.")

    all_tokens = [t for r in rows for t in r]
    avg_box_w = sum(t["bbox"][2] for t in all_tokens) / len(all_tokens)
    max_row_len = max(len(r) for r in rows)

    col_clusters = []
    cluster_threshold = max(15.0, avg_box_w * 0.4)
    x_centers = sorted([t["center"][0] for t in all_tokens])

    for x in x_centers:
        matched = False
        for cluster in col_clusters:
            if abs(x - sum(cluster) / len(cluster)) <= cluster_threshold:
                cluster.append(x)
                matched = True
                break
        if not matched:
            col_clusters.append([x])

    col_centroids = sorted([sum(c) / len(c) for c in col_clusters])
    num_cols = max(len(col_centroids), max_row_len)

    # Pad col_centroids if num_cols exceeds cluster count (avoids IndexError)
    if len(col_centroids) < num_cols:
        if col_centroids:
            spacing = col_centroids[-1] - col_centroids[0]
            avg_gap = spacing / max(len(col_centroids) - 1, 1)
        else:
            avg_gap = 50.0
        while len(col_centroids) < num_cols:
            col_centroids.append(col_centroids[-1] + avg_gap if col_centroids else 0)

    grid_matrix = []
    for r in rows:
        row_cells = [{"text": "", "value": "", "is_number": False, "bbox": None, "confidence": 0} for _ in range(num_cols)]
        for t in r:
            c_idx = min(range(num_cols), key=lambda i: abs(t["center"][0] - col_centroids[i]))
            row_cells[c_idx] = {
                "text": t["text"],
                "value": t["value"],
                "is_number": t["is_number"] or t["text"].isdigit(),
                "bbox": t["bbox"],
                "confidence": t.get("confidence", 0.5)
            }
        grid_matrix.append(row_cells)

    # Check if Row 0 contains text headers (e.g. "Q. No.", "1a", "Date", "Description", "Total")
    import re
    if grid_matrix:
        row0_texts = [cell["text"] for cell in grid_matrix[0] if cell["text"]]
        has_text_headers = any(re.search(r'[a-zA-Z]', txt) for txt in row0_texts)

        if has_text_headers and len(row0_texts) >= max(2, int(num_cols * 0.15)):
            headers = [grid_matrix[0][c]["text"] or f"Column {c+1}" for c in range(num_cols)]
            grid_matrix = grid_matrix[1:]  # remove header row from data
            print(f"[Section Detector] Freeform Mode promoted Row 0 to table headers: {headers}")
        else:
            headers = [f"Column {i+1}" for i in range(num_cols)]
    else:
        headers = [f"Column {i+1}" for i in range(num_cols)]

    return [{
        "section_id": "sec_1",
        "title": "SECTION 1",
        "bbox": [0, 0, img_shape[1], img_shape[0]],
        "headers": headers,
        "rows": grid_matrix,
        "rows_count": len(grid_matrix),
        "columns_count": num_cols
    }]
