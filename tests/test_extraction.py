"""
Quick integration test: Create a synthetic handwritten digit grid and run the
multi-pass OCR engine to verify high digit capture rate.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
import numpy as np
from backend.ocr_engine import run_ocr_on_image
from backend.section_detector import detect_sections_and_tables

def create_test_grid():
    """Creates a 5x10 grid of hand-drawn digits (simulated thick strokes)."""
    cell_w, cell_h = 50, 60
    cols, rows = 10, 5
    img_w = cols * cell_w + 2
    img_h = rows * cell_h + 2

    img = np.ones((img_h, img_w, 3), dtype=np.uint8) * 255

    # Draw grid lines
    for r in range(rows + 1):
        y = r * cell_h
        cv2.line(img, (0, y), (img_w, y), (0, 0, 0), 1)
    for c in range(cols + 1):
        x = c * cell_w
        cv2.line(img, (x, 0), (x, img_h), (0, 0, 0), 1)

    # Fill cells with digits
    digit_grid = [
        [2, 4, 3, 7, 2, 5, 7, 2, 3, 6],
        [3, 4, 3, 3, 5, 5, 0, 5, 9, 4],
        [4, 6, 3, 0, 0, 7, 3, 2, 5, 0],
        [9, 8, 3, 4, 4, 4, 0, 1, 6, 2],
        [8, 4, 1, 2, 1, 3, 5, 3, 5, 9]
    ]

    for r, row in enumerate(digit_grid):
        for c, digit in enumerate(row):
            x = c * cell_w + cell_w // 2 - 8
            y = r * cell_h + cell_h // 2 + 10
            cv2.putText(img, str(digit), (x, y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)

    return img, digit_grid

def main():
    img, expected_grid = create_test_grid()
    total_expected = sum(len(row) for row in expected_grid)

    print(f"Test grid: {len(expected_grid)} rows x {len(expected_grid[0])} cols = {total_expected} digits")
    print(f"Image size: {img.shape[1]}x{img.shape[0]}")
    print()

    # Run OCR
    tokens = run_ocr_on_image(img, is_handwritten=True, digits_only=True)
    print(f"\nTotal tokens detected: {len(tokens)}")
    
    # Run section detection
    sections = detect_sections_and_tables(tokens, img.shape)
    
    if sections:
        sec = sections[0]
        print(f"\nGrid: {sec['rows_count']} rows x {sec['columns_count']} cols")
        print(f"Headers: {sec['headers']}")
        for r_idx, row in enumerate(sec["rows"]):
            vals = [cell["text"] or "_" for cell in row]
            print(f"  Row {r_idx+1}: {vals}")
        
        # Count non-empty cells
        filled_cells = sum(1 for row in sec["rows"] for cell in row if cell["text"])
        print(f"\nFilled cells: {filled_cells}/{total_expected} ({filled_cells/total_expected*100:.0f}%)")
    else:
        print("No sections detected!")

if __name__ == "__main__":
    main()
