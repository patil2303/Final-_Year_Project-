import re
import io
import json
import datetime
import logging
import urllib.request
from typing import Dict, Any, List, Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from backend.database.mongo import (
    get_classrooms_collection,
    get_submissions_collection,
    is_live_proxy_active,
    LIVE_BASE_URL
)

logger = logging.getLogger(__name__)

STANDARD_QUESTION_HEADERS = ["1a", "1b", "1c", "1d", "1e", "1f", "2a", "2b", "3a", "3b"]


def _proxy_get(endpoint: str, timeout: int = 15) -> Any:
    url = f"{LIVE_BASE_URL}{endpoint}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (SmartLocalProxy)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _proxy_post(endpoint: str, payload: Dict[str, Any], timeout: int = 25) -> Any:
    url = f"{LIVE_BASE_URL}{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (SmartLocalProxy)"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))




def parse_numeric_roll(roll_str: Optional[str]) -> int:
    """
    Extracts the pure integer portion from composite roll numbers for natural sorting.
    Examples:
      '44 / SE' -> 44
      '44/SE' -> 44
      'SE-46' -> 46
      'B-63' -> 63
      '12' -> 12
      'Roll 5' -> 5
    """
    if not roll_str:
        return 999999
    
    # 1. Match leading digits if followed by slash or separator (e.g. "44/SE", "44 / SE")
    lead_match = re.match(r'^\s*(\d+)\s*[/_-]', str(roll_str))
    if lead_match:
        try:
            return int(lead_match.group(1))
        except ValueError:
            pass

    # 2. Match all standalone digit sequences
    digits = re.findall(r'\b\d+\b', str(roll_str))
    if digits:
        try:
            return int(digits[0])
        except ValueError:
            pass
            
    # 3. Fallback to any consecutive digits
    any_digits = re.findall(r'\d+', str(roll_str))
    if any_digits:
        try:
            return int(any_digits[0])
        except ValueError:
            pass
            
    return 999999


def clean_roll_number(roll_str: Optional[str]) -> str:
    """
    Extracts and standardizes the clean numeric roll number from composite values.
    E.g. '44 / SE' -> '44', '44/SE' -> '44', 'SE-46' -> '46', 'B-63' -> '63'.
    """
    if not roll_str:
        return ""
    num = parse_numeric_roll(roll_str)
    if num != 999999:
        return str(num)
    return str(roll_str).strip()



def parse_mark_float(val: Any) -> float:
    """Safely converts numeric or fractional mark strings ('2', '3 1/2', '1/2', '11/15') to float."""
    if not val:
        return 0.0
    s = str(val).strip()
    if not s:
        return 0.0
    if "/" in s:
        if "1/2" in s:
            base = s.replace("1/2", "").strip()
            return (float(base) if base else 0.0) + 0.5
        parts = s.split("/")
        try:
            return float(parts[0].strip())
        except ValueError:
            pass
    try:
        clean = re.sub(r'[^0-9.]', '', s)
        return float(clean) if clean else 0.0
    except ValueError:
        return 0.0


def normalize_total_marks(total_str: str, question_marks: Dict[str, Any]) -> str:
    """
    Normalizes total marks to prevent slash concatenation errors (e.g. '11/15' -> '11' or '14').
    If total is empty or zero, calculates sum from individual question marks.
    """
    s = str(total_str or "").strip()
    if "/" in s:
        if "1/2" in s:
            base = s.replace("1/2", "").strip()
            num = (float(base) if base else 0.0) + 0.5
            return str(int(num)) if num.is_integer() else str(num)
        parts = s.split("/")
        clean_num = parts[0].strip()
        if clean_num:
            return clean_num

    if not s or s == "0":
        calc_sum = 0.0
        has_any = False
        for q, v in question_marks.items():
            val = parse_mark_float(v)
            if val > 0:
                calc_sum += val
                has_any = True
        if has_any:
            return str(int(calc_sum)) if calc_sum.is_integer() else str(calc_sum)

    return s



# ==============================================================================
# CLASSROOM / BATCH MANAGEMENT (DIRECT MONGODB ATLAS SYNCHRONIZATION)
# ==============================================================================

_INMEMORY_CLASSROOMS: Dict[str, Dict[str, Any]] = {}
_INMEMORY_SUBMISSIONS: List[Dict[str, Any]] = []





def create_or_get_classroom(
    year: str,
    branch: str,
    division: str,
    semester: str,
    subject: str,
    exam_name: str = "IA-1",
    max_marks_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Registers a new classroom/exam batch or retrieves an existing one.
    Guaranteed to succeed across Local, Serverless, and In-Memory modes.
    """
    clean_yr = re.sub(r'[^A-Za-z0-9]', '', year).upper() or "SE"
    clean_br = re.sub(r'[^A-Za-z0-9]', '', branch).upper() or "IT"
    clean_div = re.sub(r'[^A-Za-z0-9]', '', division).upper() or "A"
    clean_sem = re.sub(r'[^A-Za-z0-9]', '', semester).upper() or "IV"
    clean_subj = re.sub(r'[^A-Za-z0-9]', '', subject).upper() or "CNND"
    clean_exam = re.sub(r'[^A-Za-z0-9]', '', exam_name).upper() or "IA1"
    
    classroom_id = f"{clean_yr}_{clean_br}_{clean_div}_{clean_sem}_{clean_subj}_{clean_exam}"
    
    default_max_marks = {
        "1a": "2", "1b": "2", "1c": "2", "1d": "2", "1e": "2", "1f": "2",
        "2a": "5", "2b": "5", "3a": "5", "3b": "5", "total": "20"
    }
    
    now = datetime.datetime.now(datetime.timezone.utc)
    set_fields = {
        "classroom_id": classroom_id,
        "year": year.strip().upper(),
        "branch": branch.strip().upper(),
        "division": division.strip().upper(),
        "semester": semester.strip().upper(),
        "subject": subject.strip().upper(),
        "exam_name": exam_name.strip(),
        "max_marks_config": max_marks_config or default_max_marks,
        "updated_at": now
    }
    doc = {**set_fields, "created_at": now, "is_submission_open": True}
    
    _INMEMORY_CLASSROOMS[classroom_id] = doc
    
    # Try updating MongoDB if client available
    try:
        col = get_classrooms_collection()
        if col is not None:
            col.update_one(
                {"classroom_id": classroom_id},
                {
                    "$set": set_fields,
                    "$setOnInsert": {
                        "created_at": now,
                        "is_submission_open": True
                    }
                },
                upsert=True
            )
            cls = col.find_one({"classroom_id": classroom_id}, {"_id": 0})
            if cls:
                if "is_submission_open" not in cls:
                    cls["is_submission_open"] = True
                _INMEMORY_CLASSROOMS[classroom_id] = cls
                return cls
    except Exception as e:
        logger.error(f"[MongoDB] Could not persist classroom to MongoDB ({e}), saved to memory.")

    if is_live_proxy_active():
        try:
            payload = {
                "year": year,
                "branch": branch,
                "division": division,
                "semester": semester,
                "subject": subject,
                "exam_name": exam_name or "IA-1",
                "max_marks_config": max_marks_config
            }
            res = _proxy_post("/api/classrooms", payload)
            if res and isinstance(res, dict) and res.get("classroom"):
                return res.get("classroom")
        except Exception as e:
            logger.warning(f"[Proxy] Proxy create classroom notice: {e}")

    return _INMEMORY_CLASSROOMS[classroom_id]


def toggle_classroom_submission_status(classroom_id: str, is_open: bool) -> bool:
    """Updates the submission open/closed toggle state for a classroom."""
    if classroom_id in _INMEMORY_CLASSROOMS:
        _INMEMORY_CLASSROOMS[classroom_id]["is_submission_open"] = bool(is_open)

    updated = False
    try:
        col = get_classrooms_collection()
        if col is not None:
            res = col.update_one(
                {"classroom_id": classroom_id},
                {"$set": {"is_submission_open": bool(is_open), "updated_at": datetime.datetime.now(datetime.timezone.utc)}}
            )
            updated = res.matched_count > 0 or res.modified_count > 0
    except Exception as e:
        logger.warning(f"[MongoDB] Toggle submission status notice: {e}")

    if is_live_proxy_active():
        try:
            payload = {"classroom_id": classroom_id, "is_submission_open": bool(is_open)}
            res = _proxy_post("/api/classrooms/toggle-submission", payload)
            if res and isinstance(res, dict) and res.get("status") == "success":
                updated = True
        except Exception as e:
            logger.warning(f"[Proxy] Proxy toggle submission status notice: {e}")

    return updated or (classroom_id in _INMEMORY_CLASSROOMS)


def list_classrooms() -> List[Dict[str, Any]]:
    """Returns all registered classrooms strictly fetched from MongoDB Atlas."""
    # 1. Direct MongoDB Atlas query
    try:
        col = get_classrooms_collection()
        if col is not None:
            cursor = col.find({}, {"_id": 0}).sort("created_at", -1)
            classrooms = list(cursor)
            for c in classrooms:
                if "is_submission_open" not in c:
                    c["is_submission_open"] = True
            return classrooms
    except Exception as e:
        logger.warning(f"[MongoDB] Direct list_classrooms notice: {e}")

    # 2. Live proxy query (used on local when direct MongoDB connection is blocked)
    if is_live_proxy_active():
        try:
            res = _proxy_get("/api/classrooms")
            if res and isinstance(res, dict) and "classrooms" in res:
                return res.get("classrooms", [])
        except Exception as e:
            logger.warning(f"[Proxy] Failed to proxy list_classrooms: {e}")

    # 3. If user created classrooms during this session, return them
    return list(_INMEMORY_CLASSROOMS.values())



# ==============================================================================
# STUDENT SUBMISSION MANAGEMENT (SMART UPSERT & NATURAL SORT)
# ==============================================================================

def save_or_update_submission(
    classroom_id: str,
    student_metadata: Dict[str, Any],
    marks_data: Dict[str, Any],
    raw_image_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Saves a student's extracted and verified marksheet to database / in-memory store.
    Uses smart upsert on (classroom_id, prn) or (classroom_id, roll_no).
    """
    cls_doc = _INMEMORY_CLASSROOMS.get(classroom_id)
    if cls_doc and not cls_doc.get("is_submission_open", True):
        raise PermissionError("Submissions for this exam session are currently closed by the faculty.")

    prn = str(student_metadata.get("prn", "")).strip()
    roll_no = str(student_metadata.get("roll_no", "")).strip()
    student_name = str(student_metadata.get("student_name", "")).strip().upper()
    branch = str(student_metadata.get("branch", "")).strip().upper()
    division = str(student_metadata.get("division", "")).strip().upper()
    semester = str(student_metadata.get("semester", "")).strip().upper()
    subject = str(student_metadata.get("subject", "")).strip().upper()
    
    roll_num = parse_numeric_roll(roll_no)
    
    question_marks = {}
    for k, v in marks_data.items():
        if k != "total":
            question_marks[str(k).lower()] = str(v).strip()
            
    total_marks = normalize_total_marks(marks_data.get("total", ""), question_marks)
    now = datetime.datetime.now(datetime.timezone.utc)
            
    set_fields = {
        "classroom_id": classroom_id,
        "student_name": student_name,
        "prn": prn,
        "roll_no": roll_no,
        "roll_numeric": roll_num,
        "branch": branch,
        "division": division,
        "semester": semester,
        "subject": subject,
        "marks_awarded": question_marks,
        "total_marks": total_marks,
        "status": "submitted",
        "raw_image_url": raw_image_url,
        "updated_at": now
    }
    submission_doc = {**set_fields, "submitted_at": now}
    
    existing_idx = -1
    for idx, s in enumerate(_INMEMORY_SUBMISSIONS):
        if s.get("classroom_id") == classroom_id and (
            (prn and s.get("prn") == prn) or (roll_no and s.get("roll_no") == roll_no)
        ):
            existing_idx = idx
            break
            
    if existing_idx >= 0:
        _INMEMORY_SUBMISSIONS[existing_idx].update(submission_doc)
    else:
        _INMEMORY_SUBMISSIONS.append(submission_doc)

    try:
        col = get_submissions_collection()
        if col is not None:
            filter_query = {"classroom_id": classroom_id}
            if prn:
                filter_query["prn"] = prn
            elif roll_no:
                filter_query["roll_no"] = roll_no
            else:
                filter_query["student_name"] = student_name
                
            col.update_one(
                filter_query,
                {
                    "$set": set_fields,
                    "$setOnInsert": {"submitted_at": now}
                },
                upsert=True
            )
            saved = col.find_one(filter_query, {"_id": 0})
            if saved:
                return saved
    except PermissionError:
        raise
    except Exception as e:
        logger.error(f"[MongoDB] Could not persist submission to MongoDB ({e}), saved to memory.")

    if is_live_proxy_active():
        try:
            payload = {
                "classroom_id": classroom_id,
                "student_metadata": student_metadata,
                "marks_data": marks_data
            }
            res = _proxy_post("/api/submissions", payload)
            if res and isinstance(res, dict) and res.get("submission"):
                return res.get("submission")
        except Exception as e:
            logger.warning(f"[Proxy] Proxy submission notice: {e}")

    return submission_doc


def get_classroom_submissions(classroom_id: str) -> List[Dict[str, Any]]:
    """
    Retrieves all student submissions for a classroom, strictly sorted
    by natural numeric Roll Number from MongoDB Atlas.
    """
    # 1. Direct MongoDB Atlas query
    try:
        col = get_submissions_collection()
        if col is not None:
            cursor = col.find({"classroom_id": classroom_id}, {"_id": 0})
            subs = list(cursor)
            subs.sort(key=lambda s: (
                s.get("roll_numeric") if s.get("roll_numeric") is not None and s.get("roll_numeric") != 999999
                else parse_numeric_roll(s.get("roll_no")),
                str(s.get("prn", "")),
                str(s.get("student_name", ""))
            ))
            return subs
    except Exception as e:
        logger.warning(f"[MongoDB] get_classroom_submissions error: {e}")

    # 2. Live proxy query
    if is_live_proxy_active():
        try:
            res = _proxy_get(f"/api/submissions/{classroom_id}")
            if res and isinstance(res, dict) and "submissions" in res:
                return res.get("submissions", [])
        except Exception as e:
            logger.warning(f"[Proxy] Proxy get_classroom_submissions notice: {e}")

    # 3. Session memory fallback (only what was submitted in this session)
    session_subs = [s for s in _INMEMORY_SUBMISSIONS if s.get("classroom_id") == classroom_id]
    session_subs.sort(key=lambda s: (
        s.get("roll_numeric") if s.get("roll_numeric") is not None and s.get("roll_numeric") != 999999
        else parse_numeric_roll(s.get("roll_no")),
        str(s.get("prn", "")),
        str(s.get("student_name", ""))
    ))
    return session_subs




# ==============================================================================
# MASTER EXCEL & CSV GRADE SHEET COMPILER (MULTI-STUDENT CONSOLIDATION)
# ==============================================================================

def generate_master_excel_bytes(classroom_id: str) -> bytes:
    """
    Compiles an openpyxl Master Class Grade Sheet aggregating all students
    in the classroom into one single-file Excel table sorted by Roll No.
    """
    if is_live_proxy_active():
        all_classes = list_classrooms()
        class_info = next((c for c in all_classes if c.get("classroom_id") == classroom_id), {})
    else:
        cls_col = get_classrooms_collection()
        class_info = cls_col.find_one({"classroom_id": classroom_id}, {"_id": 0}) or {}
    
    submissions = get_classroom_submissions(classroom_id)
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Master Grade Sheet"
    
    # Header Styles
    title_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    title_font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    
    max_marks_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    max_marks_font = Font(name="Calibri", size=10, bold=True, color="475569")
    
    grid_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )
    
    # Row 1: Banner
    subj = class_info.get("subject", "EXAM")
    yr = class_info.get("year", "SE")
    br = class_info.get("branch", "IT")
    div = class_info.get("division", "A")
    sem = class_info.get("semester", "IV")
    exam = class_info.get("exam_name", "IA-1")
    
    banner_title = f"{yr} {br} (DIV {div}) - {subj} (SEM {sem}) - {exam} MASTER GRADE SHEET"
    
    headers = [
        "Sr.No.", "Roll No", "PRN Number", "Student Name",
        "Branch", "Div", "Sem", "Subject",
        "1a", "1b", "1c", "1d", "1e", "1f",
        "2a", "2b", "3a", "3b",
        "Total Marks", "Status"
    ]
    
    num_cols = len(headers)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=num_cols)
    banner_cell = ws.cell(row=1, column=1, value=banner_title)
    banner_cell.fill = title_fill
    banner_cell.font = title_font
    banner_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 32
    
    # Row 2: Table Column Headers
    for c_idx, h_text in enumerate(headers, 1):
        cell = ws.cell(row=2, column=c_idx, value=h_text)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = grid_border
    ws.row_dimensions[2].height = 24
    
    # Row 3: Max Marks Row
    max_config = class_info.get("max_marks_config", {})
    max_row_vals = [
        "-", "MAX", "-", "MAX MARKS PER QUESTION",
        "-", "-", "-", "-",
        max_config.get("1a", "2"), max_config.get("1b", "2"), max_config.get("1c", "2"),
        max_config.get("1d", "2"), max_config.get("1e", "2"), max_config.get("1f", "2"),
        max_config.get("2a", "5"), max_config.get("2b", "5"),
        max_config.get("3a", "5"), max_config.get("3b", "5"),
        max_config.get("total", "20"), "-"
    ]
    
    for c_idx, val in enumerate(max_row_vals, 1):
        cell = ws.cell(row=3, column=c_idx, value=val)
        cell.fill = max_marks_fill
        cell.font = max_marks_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = grid_border
    ws.row_dimensions[3].height = 20
    
    # Rows 4..N: Student Rows (Sorted by Roll Number)
    current_r = 4
    for s_idx, sub in enumerate(submissions, 1):
        marks = sub.get("marks_awarded", {})
        
        row_data = [
            s_idx,
            sub.get("roll_no", ""),
            sub.get("prn", ""),
            sub.get("student_name", ""),
            sub.get("branch", ""),
            sub.get("division", ""),
            sub.get("semester", ""),
            sub.get("subject", ""),
            marks.get("1a", ""),
            marks.get("1b", ""),
            marks.get("1c", ""),
            marks.get("1d", ""),
            marks.get("1e", ""),
            marks.get("1f", ""),
            marks.get("2a", ""),
            marks.get("2b", ""),
            marks.get("3a", ""),
            marks.get("3b", ""),
            sub.get("total_marks", ""),
            sub.get("status", "Verified")
        ]
        
        for c_idx, val in enumerate(row_data, 1):
            cell = ws.cell(row=current_r, column=c_idx)
            # Try float/int conversion for total and numbers if possible
            if isinstance(val, (int, float)):
                cell.value = val
                cell.alignment = Alignment(horizontal="right", vertical="center")
            else:
                cell.value = str(val) if val is not None else ""
                cell.alignment = Alignment(horizontal="left" if c_idx == 4 else "center", vertical="center")
            cell.border = grid_border
            
        ws.row_dimensions[current_r].height = 20
        current_r += 1
        
    # Auto-fit column widths
    for col in ws.columns:
        col_cells = list(col)
        if not col_cells:
            continue
        max_len = max((len(str(c.value or '')) for c in col_cells[1:]), default=10)
        col_letter = get_column_letter(col_cells[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 11)
        
    ws.column_dimensions['D'].width = 30  # Generous width for full student name
    
    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def generate_master_csv_string(classroom_id: str) -> str:
    """Compiles a clean Master CSV string containing all students in the classroom."""
    submissions = get_classroom_submissions(classroom_id)
    
    headers = [
        "Sr.No.", "Roll No", "PRN Number", "Student Name",
        "Branch", "Division", "Semester", "Subject",
        "1a", "1b", "1c", "1d", "1e", "1f", "2a", "2b", "3a", "3b",
        "Total Marks", "Status"
    ]
    
    lines = [",".join(f'"{h}"' for h in headers)]
    
    for s_idx, sub in enumerate(submissions, 1):
        marks = sub.get("marks_awarded", {})
        row = [
            str(s_idx),
            str(sub.get("roll_no", "")),
            str(sub.get("prn", "")),
            str(sub.get("student_name", "")),
            str(sub.get("branch", "")),
            str(sub.get("division", "")),
            str(sub.get("semester", "")),
            str(sub.get("subject", "")),
            str(marks.get("1a", "")),
            str(marks.get("1b", "")),
            str(marks.get("1c", "")),
            str(marks.get("1d", "")),
            str(marks.get("1e", "")),
            str(marks.get("1f", "")),
            str(marks.get("2a", "")),
            str(marks.get("2b", "")),
            str(marks.get("3a", "")),
            str(marks.get("3b", "")),
            str(sub.get("total_marks", "")),
            str(sub.get("status", "Verified"))
        ]
        lines.append(",".join(f'"{val}"' for val in row))
        
    return "\n".join(lines)
