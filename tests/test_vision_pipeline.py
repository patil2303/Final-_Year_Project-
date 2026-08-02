"""
Integration test for Gemini Vision AI Extraction Pipeline.
Verifies Vision AI extraction on simulated mark sheet image data.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
import numpy as np
from backend.gemini_vision_engine import extract_with_gemini_vision

def test_pipeline():
    # Render simulated mark sheet image
    cols = ["Q.No", "1a", "1b", "1c", "1d", "1e", "1f", "2a", "2b", "3a", "3b", "Total", "Sign"]
    row1 = ["2", "2", "2", "2", "2", "2", "5", "5", "5", "5", "20", "", ""]
    row2 = ["1", "2", "2", "", "", "", "", "3", "(3)", "3", "11/15", "", "Bhoj"]

    cell_w, cell_h = 65, 45
    n_cols, n_rows = len(cols), 3
    img_w, img_h = n_cols * cell_w + 4, n_rows * cell_h + 4

    img = np.ones((img_h, img_w, 3), dtype=np.uint8) * 235
    for r in range(n_rows + 1):
        cv2.line(img, (2, r * cell_h + 2), (img_w - 2, r * cell_h + 2), (30, 30, 30), 2)
    for c in range(n_cols + 1):
        cv2.line(img, (c * cell_w + 2, 2), (c * cell_w + 2, img_h - 2), (30, 30, 30), 2)

    for c, text in enumerate(cols):
        cv2.putText(img, text, (c * cell_w + 8, cell_h // 2 + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
    for c, text in enumerate(row1):
        if text: cv2.putText(img, text, (c * cell_w + 20, cell_h + cell_h // 2 + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
    for c, text in enumerate(row2):
        if text: cv2.putText(img, text, (c * cell_w + 8, 2 * cell_h + cell_h // 2 + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2)

    print(f"Running Vision AI pipeline test on {img_w}x{img_h} image...")
    sections = extract_with_gemini_vision(img)

    assert sections is not None and len(sections) > 0, "Vision AI extraction returned None or empty sections!"

    sec = sections[0]
    print("\n--- VISION AI EXTRACTION SUCCESS ---")
    print(f"Title: {sec['title']}")
    print(f"Headers ({sec['columns_count']}): {sec['headers']}")
    for r_idx, row in enumerate(sec["rows"]):
        row_vals = [c["text"] or "_" for c in row]
        print(f"Row {r_idx+1}: {row_vals}")

    print("\nPIPELINE TEST PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_pipeline()
