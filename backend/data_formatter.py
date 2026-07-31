import io
import re
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from typing import List, Dict, Any

def convert_sections_to_dataframes(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Converts section matrix data into Pandas DataFrames with cleaned numeric types."""
    result = []

    for sec in sections:
        headers = sec.get("headers", [])
        raw_rows = sec.get("rows", [])

        # Build clean data matrix
        df_matrix = []
        for r in raw_rows:
            row_vals = []
            for cell in r:
                val = cell.get("value", "")
                if val == "":
                    row_vals.append(None)
                else:
                    row_vals.append(val)
            df_matrix.append(row_vals)

        # Create DataFrame
        if not headers and df_matrix:
            headers = [f"Col_{i+1}" for i in range(len(df_matrix[0]))]

        df = pd.DataFrame(df_matrix, columns=headers if headers else None)
        
        # Convert numeric columns where possible
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='ignore')

        result.append({
            "title": sec.get("title", "Section"),
            "dataframe": df
        })

    return result

def export_to_excel_bytes(sections: List[Dict[str, Any]]) -> bytes:
    """
    Generates a beautifully styled Excel (.xlsx) file in bytes.
    Includes custom header fills, cell number formatting, auto-column sizing,
    and multi-tab worksheets for multiple document sections.
    """
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    # Styles
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

    section_fill = PatternFill(start_color="475569", end_color="475569", fill_type="solid")
    section_font = Font(name="Calibri", size=13, bold=True, color="FFFFFF")

    grid_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    # 1. Master Sheet (All Sections Stacked)
    ws_master = wb.create_sheet(title="Summary")
    current_row = 1

    for sec in sections:
        title = sec.get("title", "Section")
        headers = sec.get("headers", [])
        rows = sec.get("rows", [])

        # Section Header Banner
        num_cols = max(len(headers), 1)
        ws_master.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=num_cols)
        banner_cell = ws_master.cell(row=current_row, column=1, value=title.upper())
        banner_cell.fill = section_fill
        banner_cell.font = section_font
        banner_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws_master.row_dimensions[current_row].height = 28
        current_row += 1

        # Table Column Headers
        if headers:
            for c_idx, h_text in enumerate(headers, 1):
                cell = ws_master.cell(row=current_row, column=c_idx, value=str(h_text))
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = grid_border
            ws_master.row_dimensions[current_row].height = 22
            current_row += 1

        # Table Rows
        for r_idx, r_cells in enumerate(rows, 1):
            for c_idx, c_info in enumerate(r_cells, 1):
                val = c_info.get("value", "")
                cell = ws_master.cell(row=current_row, column=c_idx)

                # Set numeric or text value
                if isinstance(val, (int, float)):
                    cell.value = val
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                    if isinstance(val, float):
                        cell.number_format = '#,##0.00'
                    else:
                        cell.number_format = '#,##0'
                else:
                    cell.value = str(val) if val is not None else ""
                    cell.alignment = Alignment(horizontal="left", vertical="center")

                cell.border = grid_border
            ws_master.row_dimensions[current_row].height = 20
            current_row += 1

        # Gap between sections
        current_row += 2

    # Auto-adjust column widths for Summary sheet
    for col in ws_master.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or '')
            max_len = max(max_len, len(val_str))
        ws_master.column_dimensions[col_letter].width = max(max_len + 4, 12)

    # 2. Separate Sheets for each section if more than 1 section
    if len(sections) > 1:
        for idx, sec in enumerate(sections, 1):
            raw_title = sec.get("title", f"Section_{idx}")
            sheet_title = re.sub(r'[\:\\/\?\*\[\]]', '_', raw_title)[:30] or f"Sheet_{idx}"
            
            ws = wb.create_sheet(title=sheet_title)
            headers = sec.get("headers", [])
            rows = sec.get("rows", [])

            # Write headers
            if headers:
                for c_idx, h_text in enumerate(headers, 1):
                    cell = ws.cell(row=1, column=c_idx, value=str(h_text))
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.border = grid_border

            # Write rows
            start_r = 2 if headers else 1
            for r_idx, r_cells in enumerate(rows, start_r):
                for c_idx, c_info in enumerate(r_cells, 1):
                    val = c_info.get("value", "")
                    cell = ws.cell(row=r_idx, column=c_idx)
                    if isinstance(val, (int, float)):
                        cell.value = val
                        cell.alignment = Alignment(horizontal="right")
                    else:
                        cell.value = str(val) if val is not None else ""
                    cell.border = grid_border

            # Auto-adjust column widths (guard against empty sheets)
            for col in ws.columns:
                col_cells = list(col)
                if not col_cells:
                    continue
                max_len = max((len(str(cell.value or '')) for cell in col_cells), default=0)
                col_letter = get_column_letter(col_cells[0].column)
                ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()

def _sanitize_csv_value(val) -> str:
    """Sanitizes a value to prevent CSV formula injection in spreadsheet applications."""
    s = str(val) if val is not None else ""
    # If the value starts with a formula trigger character, prefix with a single quote
    if s and s[0] in ('=', '+', '-', '@', '\t', '\r', '\n'):
        # Check if it's a legitimate negative number
        try:
            float(s)
            return s  # legitimate number like "-5.3"
        except (ValueError, TypeError):
            return "'" + s  # escape formula
    return s

def export_to_csv_string(sections: List[Dict[str, Any]]) -> str:
    """Generates clean CSV text with section boundary titles."""
    lines = []
    for sec in sections:
        title = sec.get("title", "Section")
        lines.append(f"# --- SECTION: {title} ---")

        headers = sec.get("headers", [])
        if headers:
            lines.append(",".join(f'"{ _sanitize_csv_value(h)}"' for h in headers))

        rows = sec.get("rows", [])
        for r in rows:
            row_vals = []
            for cell in r:
                val = cell.get("value", "")
                sanitized = _sanitize_csv_value(val)
                row_vals.append(f'"{sanitized}"' if isinstance(val, str) else str(sanitized))
            lines.append(",".join(row_vals))

        lines.append("")  # Blank line separator

    return "\n".join(lines)
