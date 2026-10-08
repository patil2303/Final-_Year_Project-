import os
import json
import hmac
import hashlib
import datetime
import logging
import smtplib
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional

from backend.database.mongo import (
    get_users_collection,
    is_live_proxy_active,
    LIVE_BASE_URL
)

logger = logging.getLogger(__name__)

# Primary Admin Email configured as requested
ADMIN_EMAIL = "hp5623699@gmail.com"
DEFAULT_ADMIN_PASSWORD = os.environ.get("ADMIN_DEFAULT_PASSWORD", "Admin@123")
SECRET_SALT = os.environ.get("AUTH_SECRET_SALT", "academic_marksheet_portal_salt_2026")

# Local fallback file in case of offline local development
_LOCAL_USERS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "local_users_cache.json"
)


def _hash_password(password: str) -> str:
    """Creates a salted SHA-256 hash of the password."""
    salted = f"{SECRET_SALT}:{password}".encode("utf-8")
    return hashlib.sha256(salted).hexdigest()


def _generate_session_token(email: str, role: str) -> str:
    """Generates a deterministic HMAC token for session validation."""
    msg = f"{email.lower().strip()}:{role.lower().strip()}".encode("utf-8")
    return hmac.new(SECRET_SALT.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def verify_session_token(email: str, role: str, token: str) -> bool:
    """Verifies a session token."""
    if not email or not role or not token:
        return False
    expected = _generate_session_token(email, role)
    return hmac.compare_digest(expected, token)


def _proxy_get(endpoint: str, timeout: int = 12) -> Any:
    url = f"{LIVE_BASE_URL}{endpoint}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (SmartLocalProxy)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _proxy_post(endpoint: str, payload: Dict[str, Any], timeout: int = 15) -> Any:
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


def _load_local_users() -> Dict[str, Dict[str, Any]]:
    """Loads local fallback user store and ensures ADMIN_EMAIL is present."""
    users: Dict[str, Dict[str, Any]] = {}
    if os.path.exists(_LOCAL_USERS_FILE):
        try:
            with open(_LOCAL_USERS_FILE, "r", encoding="utf-8") as f:
                users = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load local users cache: {e}")

    if ADMIN_EMAIL not in users:
        now_iso = datetime.datetime.utcnow().isoformat() + "Z"
        users[ADMIN_EMAIL] = {
            "name": "System Administrator",
            "email": ADMIN_EMAIL,
            "password_hash": _hash_password(DEFAULT_ADMIN_PASSWORD),
            "role": "admin",
            "requested_role": "admin",
            "status": "approved",
            "department": "Administration",
            "roll_or_id": "ADMIN-01",
            "reason": "Primary System Administrator",
            "created_at": now_iso,
            "updated_at": now_iso,
            "approved_by": ADMIN_EMAIL
        }
        _save_local_users(users)
    return users


def _save_local_users(users: Dict[str, Dict[str, Any]]) -> None:
    try:
        with open(_LOCAL_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save local users cache: {e}")


def _sanitize_user(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Removes sensitive fields like password_hash and MongoDB _id before returning."""
    if not doc:
        return {}
    clean = dict(doc)
    clean.pop("_id", None)
    clean.pop("password_hash", None)
    return clean


def _ensure_admin_exists(col) -> None:
    """Ensures the primary admin account (hp5623699@gmail.com) exists in MongoDB."""
    if col is None:
        return
    try:
        existing = col.find_one({"email": ADMIN_EMAIL})
        if not existing:
            now_iso = datetime.datetime.utcnow().isoformat() + "Z"
            col.insert_one({
                "name": "System Administrator",
                "email": ADMIN_EMAIL,
                "password_hash": _hash_password(DEFAULT_ADMIN_PASSWORD),
                "role": "admin",
                "requested_role": "admin",
                "status": "approved",
                "department": "IT / Administration",
                "roll_or_id": "ADMIN-01",
                "reason": "Primary Portal Administrator",
                "created_at": now_iso,
                "updated_at": now_iso,
                "approved_by": ADMIN_EMAIL
            })
            logger.info(f"[Auth] Seeded primary admin account: {ADMIN_EMAIL}")
        elif existing.get("role") != "admin" or existing.get("status") != "approved":
            col.update_one(
                {"email": ADMIN_EMAIL},
                {"$set": {"role": "admin", "status": "approved", "requested_role": "admin"}}
            )
    except Exception as e:
        logger.warning(f"[Auth] Ensure admin notice: {e}")


def _try_send_email_notification(subject: str, recipient_email: str, html_body: str) -> bool:
    """
    Attempts to send an email via SMTP if SMTP_EMAIL and SMTP_PASSWORD are set in environment.
    Returns True if sent, False otherwise (never raises exception).
    """
    smtp_user = os.environ.get("SMTP_EMAIL", "").strip()
    smtp_pass = os.environ.get("SMTP_PASSWORD", "").strip()
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))

    if not smtp_user or not smtp_pass:
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = recipient_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=8) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [recipient_email], msg.as_string())
        logger.info(f"[Auth Email] Sent email notification to {recipient_email}")
        return True
    except Exception as e:
        logger.warning(f"[Auth Email] SMTP notification skipped/failed: {e}")
        return False


def register_join_request(
    name: str,
    email: str,
    password: str,
    requested_role: str,
    department: str = "",
    roll_or_id: str = "",
    reason: str = ""
) -> Dict[str, Any]:
    """
    Submits a new user join request for 'student' or 'faculty' role.
    If the email is ADMIN_EMAIL (hp5623699@gmail.com), automatically grants 'admin' role and approves immediately.
    """
    clean_email = (email or "").strip().lower()
    clean_name = (name or "").strip()
    req_role = (requested_role or "student").strip().lower()

    if not clean_email or "@" not in clean_email:
        raise ValueError("Please provide a valid email address.")
    if not clean_name:
        raise ValueError("Please provide your full name.")
    if not password or len(password) < 4:
        raise ValueError("Password must be at least 4 characters long.")

    if req_role not in ("student", "faculty", "admin"):
        req_role = "student"

    is_admin_email = (clean_email == ADMIN_EMAIL.lower())
    final_role = "admin" if is_admin_email else req_role
    final_status = "approved" if is_admin_email else "pending"
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"
    pw_hash = _hash_password(password)

    col = get_users_collection()
    if col is not None:
        _ensure_admin_exists(col)
        existing = col.find_one({"email": clean_email})

        if existing:
            if is_admin_email:
                col.update_one(
                    {"email": clean_email},
                    {"$set": {
                        "name": clean_name,
                        "password_hash": pw_hash,
                        "role": "admin",
                        "requested_role": "admin",
                        "status": "approved",
                        "updated_at": now_iso
                    }}
                )
                updated_doc = col.find_one({"email": clean_email})
                user_clean = _sanitize_user(updated_doc)
                return {
                    "status": "approved",
                    "message": "Admin account configured and approved.",
                    "user": user_clean,
                    "token": _generate_session_token(clean_email, "admin")
                }

            if existing.get("status") == "approved":
                raise ValueError(
                    f"An approved account for {clean_email} already exists with role '{existing.get('role', 'student').upper()}'. Please sign in on the Login tab."
                )

            # Update existing pending or rejected request
            col.update_one(
                {"email": clean_email},
                {"$set": {
                    "name": clean_name,
                    "password_hash": pw_hash,
                    "requested_role": req_role,
                    "role": req_role,
                    "status": "pending",
                    "department": department.strip(),
                    "roll_or_id": roll_or_id.strip(),
                    "reason": reason.strip(),
                    "updated_at": now_iso
                }}
            )
            doc = col.find_one({"email": clean_email})
        else:
            new_doc = {
                "name": clean_name,
                "email": clean_email,
                "password_hash": pw_hash,
                "role": final_role,
                "requested_role": final_role,
                "status": final_status,
                "department": department.strip(),
                "roll_or_id": roll_or_id.strip(),
                "reason": reason.strip(),
                "created_at": now_iso,
                "updated_at": now_iso,
                "approved_by": ADMIN_EMAIL if is_admin_email else None
            }
            col.insert_one(new_doc)
            doc = new_doc
    else:
        # Local fallback
        users = _load_local_users()
        existing = users.get(clean_email)
        if existing and not is_admin_email and existing.get("status") == "approved":
            raise ValueError(
                f"An approved account for {clean_email} already exists. Please sign in on the Login tab."
            )
        doc = {
            "name": clean_name,
            "email": clean_email,
            "password_hash": pw_hash,
            "role": final_role,
            "requested_role": final_role,
            "status": final_status,
            "department": department.strip(),
            "roll_or_id": roll_or_id.strip(),
            "reason": reason.strip(),
            "created_at": existing.get("created_at", now_iso) if existing else now_iso,
            "updated_at": now_iso,
            "approved_by": ADMIN_EMAIL if is_admin_email else None
        }
        users[clean_email] = doc
        _save_local_users(users)

    # Also mirror to local cache for offline resilience
    try:
        users = _load_local_users()
        users[clean_email] = dict(doc)
        users[clean_email].pop("_id", None)
        _save_local_users(users)
    except Exception:
        pass

    # Attempt optional SMTP email to Admin
    email_sent = False
    if not is_admin_email:
        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; padding: 20px; border: 1px solid #e2e8f0; border-radius: 10px;">
            <h2 style="color: #1e40af; margin-top: 0;">New Portal Role Join Request</h2>
            <p>A new user has requested access to the <strong>Academic Exam & Marksheet Portal</strong>:</p>
            <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Full Name:</strong></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{clean_name}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Email:</strong></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{clean_email}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Requested Role:</strong></td><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong style="color: #2563eb;">{req_role.upper()}</strong></td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Department / Branch:</strong></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{department or 'N/A'}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Roll No / ID:</strong></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{roll_or_id or 'N/A'}</td></tr>
            </table>
            <p>Please log into the <strong>Admin Control Panel</strong> ({ADMIN_EMAIL}) to verify and approve this request.</p>
        </div>
        """
        email_sent = _try_send_email_notification(
            subject=f"[Portal Join Request] {clean_name} requested {req_role.upper()} role",
            recipient_email=ADMIN_EMAIL,
            html_body=html_body
        )

    user_clean = _sanitize_user(doc)
    result = {
        "status": final_status,
        "admin_email": ADMIN_EMAIL,
        "email_notification_sent": email_sent,
        "user": user_clean,
        "message": (
            "Admin account active!"
            if is_admin_email
            else f"Join request for {req_role.upper()} role sent to Admin ({ADMIN_EMAIL}). Waiting for approval."
        )
    }
    if is_admin_email:
        result["token"] = _generate_session_token(clean_email, "admin")
    return result


def authenticate_user(email: str, password: str) -> Dict[str, Any]:
    """
    Authenticates a user by email and password.
    Checks approval status and returns role & token if approved.
    """
    clean_email = (email or "").strip().lower()
    if not clean_email or not password:
        raise ValueError("Please enter both email and password.")

    pw_hash = _hash_password(password)
    doc = None

    col = get_users_collection()
    if col is not None:
        _ensure_admin_exists(col)
        doc = col.find_one({"email": clean_email})

    if doc is None:
        users = _load_local_users()
        doc = users.get(clean_email)

    if not doc:
        raise ValueError("No account or join request found for this email. Please submit a Join Request first.")

    # Verify password (for ADMIN_EMAIL, also allow default password if not custom-set)
    stored_hash = doc.get("password_hash", "")
    if stored_hash != pw_hash:
        raise ValueError("Invalid password. Please check your credentials and try again.")

    status = doc.get("status", "pending")
    role = doc.get("role", doc.get("requested_role", "student"))
    if clean_email == ADMIN_EMAIL.lower():
        status = "approved"
        role = "admin"

    user_clean = _sanitize_user(doc)
    user_clean["status"] = status
    user_clean["role"] = role

    if status == "pending":
        return {
            "status": "pending",
            "admin_email": ADMIN_EMAIL,
            "user": user_clean,
            "message": f"Your join request for the {role.upper()} role is currently pending approval by Admin ({ADMIN_EMAIL})."
        }

    if status == "rejected":
        return {
            "status": "rejected",
            "admin_email": ADMIN_EMAIL,
            "user": user_clean,
            "message": f"Your join request was declined by the Administrator ({ADMIN_EMAIL})."
        }

    token = _generate_session_token(clean_email, role)
    return {
        "status": "approved",
        "admin_email": ADMIN_EMAIL,
        "user": user_clean,
        "token": token,
        "message": f"Welcome back, {user_clean.get('name', 'User')}!"
    }


def get_user_status(email: str) -> Dict[str, Any]:
    """Returns the latest status and role for a given email."""
    clean_email = (email or "").strip().lower()
    if not clean_email:
        raise ValueError("Email is required.")

    doc = None
    col = get_users_collection()
    if col is not None:
        _ensure_admin_exists(col)
        doc = col.find_one({"email": clean_email})

    if doc is None:
        users = _load_local_users()
        doc = users.get(clean_email)

    if not doc:
        return {"status": "not_found", "email": clean_email}

    status = doc.get("status", "pending")
    role = doc.get("role", doc.get("requested_role", "student"))
    if clean_email == ADMIN_EMAIL.lower():
        status = "approved"
        role = "admin"

    user_clean = _sanitize_user(doc)
    user_clean["status"] = status
    user_clean["role"] = role

    res = {
        "status": status,
        "user": user_clean,
        "admin_email": ADMIN_EMAIL
    }
    if status == "approved":
        res["token"] = _generate_session_token(clean_email, role)
    return res


def list_all_users(admin_email: str) -> Dict[str, Any]:
    """
    Lists all registered users and join requests for the Admin Control Panel.
    Only accessible by ADMIN_EMAIL (hp5623699@gmail.com).
    """
    if (admin_email or "").strip().lower() != ADMIN_EMAIL.lower():
        raise PermissionError(f"Unauthorized: Only {ADMIN_EMAIL} can access Admin User Management.")

    docs: List[Dict[str, Any]] = []
    col = get_users_collection()
    if col is not None:
        _ensure_admin_exists(col)
        cursor = col.find({})
        for d in cursor:
            docs.append(_sanitize_user(d))
    else:
        users = _load_local_users()
        docs = [_sanitize_user(u) for u in users.values()]

    # Sort: pending first, then by updated_at / created_at descending
    status_priority = {"pending": 0, "approved": 1, "rejected": 2}
    docs.sort(
        key=lambda x: (
            status_priority.get(x.get("status", "pending"), 9),
            -(int(datetime.datetime.fromisoformat(x["created_at"].replace("Z", "")).timestamp())
              if x.get("created_at") and "T" in str(x.get("created_at"))
              else 0)
        )
    )

    pending_count = sum(1 for u in docs if u.get("status") == "pending")
    approved_faculty = sum(1 for u in docs if u.get("status") == "approved" and u.get("role") == "faculty")
    approved_students = sum(1 for u in docs if u.get("status") == "approved" and u.get("role") == "student")
    rejected_count = sum(1 for u in docs if u.get("status") == "rejected")

    return {
        "status": "success",
        "admin_email": ADMIN_EMAIL,
        "summary": {
            "total": len(docs),
            "pending": pending_count,
            "approved_faculty": approved_faculty,
            "approved_students": approved_students,
            "rejected": rejected_count
        },
        "users": docs
    }


def update_user_access(
    admin_email: str,
    target_email: str,
    action: str,
    assigned_role: Optional[str] = None
) -> Dict[str, Any]:
    """
    Allows Admin (hp5623699@gmail.com) to approve, reject, revoke, or change role for a user.
    action: 'approve' | 'reject' | 'change_role' | 'pending'
    assigned_role: 'student' | 'faculty' | 'admin'
    """
    if (admin_email or "").strip().lower() != ADMIN_EMAIL.lower():
        raise PermissionError(f"Unauthorized: Only {ADMIN_EMAIL} can modify user roles and approvals.")

    clean_target = (target_email or "").strip().lower()
    if not clean_target:
        raise ValueError("Target user email is required.")

    if clean_target == ADMIN_EMAIL.lower() and action in ("reject", "pending"):
        raise ValueError("Cannot revoke or reject the primary Administrator account.")

    now_iso = datetime.datetime.utcnow().isoformat() + "Z"
    col = get_users_collection()
    doc = None

    if col is not None:
        doc = col.find_one({"email": clean_target})

    if doc is None:
        users = _load_local_users()
        doc = users.get(clean_target)

    if not doc:
        raise ValueError(f"User {clean_target} not found.")

    new_role = (assigned_role or doc.get("role") or doc.get("requested_role") or "student").strip().lower()
    if new_role not in ("student", "faculty", "admin"):
        new_role = "student"

    if action == "approve":
        new_status = "approved"
    elif action == "reject":
        new_status = "rejected"
    elif action == "pending":
        new_status = "pending"
    elif action == "change_role":
        new_status = doc.get("status", "approved")
    else:
        raise ValueError(f"Invalid action: {action}")

    update_fields = {
        "status": new_status,
        "role": new_role,
        "updated_at": now_iso,
        "approved_by": ADMIN_EMAIL
    }

    if col is not None:
        col.update_one({"email": clean_target}, {"$set": update_fields})
        updated_doc = col.find_one({"email": clean_target})
    else:
        users = _load_local_users()
        users[clean_target].update(update_fields)
        _save_local_users(users)
        updated_doc = users[clean_target]

    # Sync local cache
    try:
        users = _load_local_users()
        if clean_target in users:
            users[clean_target].update(update_fields)
            _save_local_users(users)
    except Exception:
        pass

    # Optional SMTP notification to the user upon approval
    if new_status == "approved":
        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; padding: 20px; border: 1px solid #e2e8f0; border-radius: 10px;">
            <h2 style="color: #16a34a; margin-top: 0;">Your Portal Join Request Has Been Approved!</h2>
            <p>Hello <strong>{updated_doc.get('name', 'User')}</strong>,</p>
            <p>The Portal Administrator (<strong>{ADMIN_EMAIL}</strong>) has verified and approved your account.</p>
            <p><strong>Assigned Role:</strong> <span style="color: #2563eb; font-weight: bold;">{new_role.upper()}</span></p>
            <p>You can now sign in with your registered email and password.</p>
        </div>
        """
        _try_send_email_notification(
            subject=f"Access Approved: {new_role.upper()} Role Granted — Academic Marksheet Portal",
            recipient_email=clean_target,
            html_body=html_body
        )

    return {
        "status": "success",
        "message": f"User {clean_target} updated: status={new_status.upper()}, role={new_role.upper()}",
        "user": _sanitize_user(updated_doc)
    }


def admin_create_user(
    admin_email: str,
    name: str,
    email: str,
    password: str,
    role: str,
    department: str = "",
    roll_or_id: str = ""
) -> Dict[str, Any]:
    """Allows Admin to directly create and pre-approve a Student or Faculty account."""
    if (admin_email or "").strip().lower() != ADMIN_EMAIL.lower():
        raise PermissionError(f"Unauthorized: Only {ADMIN_EMAIL} can directly create users.")

    clean_email = (email or "").strip().lower()
    clean_name = (name or "").strip()
    clean_role = (role or "student").strip().lower()
    if clean_role not in ("student", "faculty", "admin"):
        clean_role = "student"

    if not clean_email or "@" not in clean_email:
        raise ValueError("Valid email address is required.")
    if not clean_name:
        raise ValueError("Full name is required.")
    if not password or len(password) < 4:
        raise ValueError("Password must be at least 4 characters.")

    now_iso = datetime.datetime.utcnow().isoformat() + "Z"
    pw_hash = _hash_password(password)

    user_doc = {
        "name": clean_name,
        "email": clean_email,
        "password_hash": pw_hash,
        "role": clean_role,
        "requested_role": clean_role,
        "status": "approved",
        "department": department.strip(),
        "roll_or_id": roll_or_id.strip(),
        "reason": "Directly created and approved by Admin",
        "created_at": now_iso,
        "updated_at": now_iso,
        "approved_by": ADMIN_EMAIL
    }

    col = get_users_collection()
    if col is not None:
        col.update_one({"email": clean_email}, {"$set": user_doc}, upsert=True)
    users = _load_local_users()
    users[clean_email] = dict(user_doc)
    _save_local_users(users)

    return {
        "status": "success",
        "message": f"Created and pre-approved {clean_role.upper()} account for {clean_email}.",
        "user": _sanitize_user(user_doc)
    }


def delete_user_account(admin_email: str, target_email: str) -> Dict[str, Any]:
    """Allows Admin to delete a user request or account."""
    if (admin_email or "").strip().lower() != ADMIN_EMAIL.lower():
        raise PermissionError(f"Unauthorized: Only {ADMIN_EMAIL} can delete user accounts.")

    clean_target = (target_email or "").strip().lower()
    if clean_target == ADMIN_EMAIL.lower():
        raise ValueError("Cannot delete the primary Administrator account.")

    col = get_users_collection()
    if col is not None:
        col.delete_one({"email": clean_target})

    users = _load_local_users()
    if clean_target in users:
        del users[clean_target]
        _save_local_users(users)

    return {
        "status": "success",
        "message": f"Deleted user account/request for {clean_target}."
    }
