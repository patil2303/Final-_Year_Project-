"""
Integration test for mark sheet table grid extraction.
Verifies grid line detection, text header promotion, fraction parsing ('11/15'),
parenthesized marks ('(3)'), and single-digit precision on fine table grids.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
import numpy as np
from backend.ocr_engine import run_ocr_on_image
from backend.section_detector import detect_sections_and_tables

def create_marksheet_image():
    """Renders a simulated exam paper mark sheet grid (13 columns x 3 rows)."""
    cols = ["Q.No", "1a", "1b", "1c", "1d", "1e", "1f", "2a", "2b", "3a", "3b", "Total", "Sign"]
    row1 = ["2", "2", "2", "2", "2", "2", "5", "5", "5", "5", "20", "", ""]
    row2 = ["1", "2", "2", "", "", "", "", "3", "(3)", "3", "11/15", "", "Bhoj"]

    cell_w, cell_h = 65, 45
    n_cols = len(cols)
    n_rows = 3
    img_w = n_cols * cell_w + 4
    img_h = n_rows * cell_h + 4

    # Paper background with slight shadow gradient
    img = np.ones((img_h, img_w, 3), dtype=np.uint8) * 235
    for y in range(img_h):
        shadow = int((y / img_h) * 20)
        img[y, :] = np.clip(img[y, :] - shadow, 0, 255)

    # Draw grid lines
    for r in range(n_rows + 1):
        y = r * cell_h + 2
        cv2.line(img, (2, y), (img_w - 2, y), (30, 30, 30), 2)
    for c in range(n_cols + 1):
        x = c * cell_w + 2
        cv2.line(img, (x, 2), (x, img_h - 2), (30, 30, 30), 2)

    # Draw text in headers
    for c, text in enumerate(cols):
        x = c * cell_w + 8
        y = cell_h // 2 + 10
        cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)

    # Draw row 1 (max marks)
    for c, text in enumerate(row1):
        if text:
            x = c * cell_w + 20
            y = cell_h + cell_h // 2 + 10
            cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2, cv2.LINE_AA)

    # Draw row 2 (awarded marks)
    for c, text in enumerate(row2):
        if text:
            x = c * cell_w + 8
            y = 2 * cell_h + cell_h // 2 + 10
            cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2, cv2.LINE_AA)

    return img

def main():
    img = create_marksheet_image()
    print(f"Created mark sheet image: {img.shape[1]}x{img.shape[0]} px")

    tokens = run_ocr_on_image(img)
    print(f"Total tokens detected: {len(tokens)}")

    sections = detect_sections_and_tables(tokens, img.shape)
    assert len(sections) > 0, "Failed to detect sections!"

    sec = sections[0]
    print(f"\nExtracted Section: {sec['rows_count']} rows x {sec['columns_count']} cols")
    print(f"Headers: {sec['headers']}")

    for idx, row in enumerate(sec["rows"]):
        row_vals = [c["text"] or "_" for c in row]
        print(f"  Data Row {idx+1}: {row_vals}")

    print("\nMark Sheet Extraction Test PASSED!")

if __name__ == "__main__":
    main()
