import os
import cv2
import numpy as np

def create_sample_table_image(output_path: str):
    """Generates a synthetic sample table photo with numbers and sections."""
    img = np.ones((700, 950, 3), dtype=np.uint8) * 255

    # Section 1 Header
    cv2.putText(img, "SECTION 1: MONTHLY SALES SUMMARY 2026", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (30, 41, 59), 2)

    # Table 1 Header
    cv2.rectangle(img, (50, 75), (900, 115), (240, 245, 250), -1)
    cv2.rectangle(img, (50, 75), (900, 115), (71, 85, 105), 2)

    headers1 = ["Month", "Units Sold", "Unit Price ($)", "Total Revenue ($)", "Margin (%)"]
    col_x = [60, 230, 400, 580, 770]
    for i, h in enumerate(headers1):
        cv2.putText(img, h, (col_x[i], 102), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (15, 23, 42), 2)

    # Table 1 Rows
    rows1 = [
        ["Jan 2026", "1450", "25.00", "36250.00", "32.5"],
        ["Feb 2026", "1680", "25.00", "42000.00", "34.1"],
        ["Mar 2026", "1920", "24.50", "47040.00", "35.8"],
        ["Apr 2026", "2100", "24.50", "51450.00", "36.2"]
    ]

    for r_idx, r in enumerate(rows1):
        y = 115 + (r_idx * 38)
        cv2.rectangle(img, (50, y), (900, y + 38), (200, 200, 200), 1)
        for c_idx, val in enumerate(r):
            cv2.putText(img, val, (col_x[c_idx], y + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (30, 41, 59), 1)

    # Section 2 Header
    cv2.putText(img, "SECTION 2: MATRIX ARRAY PARAMETERS", (50, 330), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (30, 41, 59), 2)

    # Table 2 Header
    cv2.rectangle(img, (50, 355), (900, 395), (240, 245, 250), -1)
    cv2.rectangle(img, (50, 355), (900, 395), (71, 85, 105), 2)

    headers2 = ["Node ID", "Alpha Factor", "Beta Ratio", "Gamma Value", "Delta Threshold"]
    for i, h in enumerate(headers2):
        cv2.putText(img, h, (col_x[i], 382), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (15, 23, 42), 2)

    # Table 2 Rows
    rows2 = [
        ["NODE-A", "0.0142", "1.850", "98.42", "-12.5"],
        ["NODE-B", "0.0189", "2.104", "104.15", "-10.2"],
        ["NODE-C", "0.0215", "2.440", "112.60", "-8.7"],
        ["NODE-D", "0.0260", "2.980", "125.80", "-5.4"]
    ]

    for r_idx, r in enumerate(rows2):
        y = 395 + (r_idx * 38)
        cv2.rectangle(img, (50, y), (900, y + 38), (200, 200, 200), 1)
        for c_idx, val in enumerate(r):
            cv2.putText(img, val, (col_x[c_idx], y + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (30, 41, 59), 1)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cv2.imwrite(output_path, img)
    print(f"Sample table photo created at: {output_path}")

if __name__ == "__main__":
    create_sample_table_image("sample_images/sample_financial_table.png")
