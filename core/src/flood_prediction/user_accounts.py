"""
user_accounts.py — User registration and personalized alert management.

Features:
  - Register with phone or email
  - Set home district for personalized alerts
  - Choose alert severity threshold (HIGH or CRITICAL)
  - Alert history and acknowledgment tracking
  - SQLite-backed — no external auth service needed
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# ── DB schema ─────────────────────────────────────────────────────────────────
USER_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    email           TEXT UNIQUE,
    phone           TEXT UNIQUE,
    password_hash   TEXT NOT NULL,
    home_district   TEXT,
    home_state      TEXT,
    language        TEXT DEFAULT 'en',
    alert_threshold TEXT DEFAULT 'HIGH',
    alert_sms       INTEGER DEFAULT 1,
    alert_email     INTEGER DEFAULT 1,
    alert_whatsapp  INTEGER DEFAULT 0,
    is_active       INTEGER DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login      TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    alert_type      TEXT NOT NULL,
    district        TEXT,
    message         TEXT NOT NULL,
    severity        TEXT NOT NULL,
    channel         TEXT DEFAULT 'system',
    is_read         INTEGER DEFAULT 0,
    acknowledged_at TIMESTAMP,
    sent_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    token           TEXT UNIQUE NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at      TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_users_email   ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_phone   ON users(phone);
CREATE INDEX IF NOT EXISTS idx_alerts_user   ON user_alerts(user_id, sent_at);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(token);
"""


def _conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_user_tables(db_path: str) -> None:
    """Create user tables if they don't exist."""
    with _conn(db_path) as conn:
        conn.executescript(USER_SCHEMA)


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{h}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split(":", 1)
        return hashlib.sha256(f"{salt}{password}".encode()).hexdigest() == h
    except Exception:
        return False


# ── User CRUD ─────────────────────────────────────────────────────────────────

def register_user(db_path: str, name: str, password: str,
                  email: Optional[str] = None,
                  phone: Optional[str] = None,
                  home_district: Optional[str] = None,
                  home_state: Optional[str] = None,
                  language: str = "en",
                  alert_threshold: str = "HIGH") -> Dict[str, Any]:
    """Register a new user. Returns user dict or raises ValueError."""
    if not email and not phone:
        raise ValueError("Email or phone number is required")
    if not name.strip():
        raise ValueError("Name is required")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters")

    pw_hash = _hash_password(password)

    try:
        with _conn(db_path) as conn:
            cur = conn.execute(
                """INSERT INTO users
                   (name, email, phone, password_hash, home_district, home_state,
                    language, alert_threshold)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (name.strip(), email, phone, pw_hash,
                 home_district, home_state, language, alert_threshold)
            )
            user_id = cur.lastrowid
            return get_user_by_id(db_path, user_id)
    except sqlite3.IntegrityError as e:
        if "email" in str(e):
            raise ValueError("Email already registered")
        if "phone" in str(e):
            raise ValueError("Phone number already registered")
        raise ValueError(str(e))


def login_user(db_path: str, identifier: str,
               password: str) -> Optional[Dict[str, Any]]:
    """
    Login by email or phone. Returns user dict + session token, or None.
    """
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE (email=? OR phone=?) AND is_active=1",
            (identifier, identifier)
        ).fetchone()

        if not row or not _verify_password(password, row["password_hash"]):
            return None

        # Create session token
        token = secrets.token_urlsafe(32)
        conn.execute(
            """INSERT INTO user_sessions (user_id, token, expires_at)
               VALUES (?, ?, datetime('now', '+30 days'))""",
            (row["id"], token)
        )
        conn.execute(
            "UPDATE users SET last_login=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), row["id"])
        )

        user = dict(row)
        user.pop("password_hash", None)
        user["session_token"] = token
        return user


def get_user_by_token(db_path: str, token: str) -> Optional[Dict[str, Any]]:
    """Get user from session token."""
    with _conn(db_path) as conn:
        row = conn.execute(
            """SELECT u.* FROM users u
               JOIN user_sessions s ON u.id = s.user_id
               WHERE s.token=? AND s.expires_at > datetime('now')
               AND u.is_active=1""",
            (token,)
        ).fetchone()
        if not row:
            return None
        user = dict(row)
        user.pop("password_hash", None)
        return user


def get_user_by_id(db_path: str, user_id: int) -> Optional[Dict[str, Any]]:
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id=?", (user_id,)
        ).fetchone()
        if not row:
            return None
        user = dict(row)
        user.pop("password_hash", None)
        return user


def update_user_preferences(db_path: str, user_id: int,
                             home_district: Optional[str] = None,
                             home_state: Optional[str] = None,
                             language: Optional[str] = None,
                             alert_threshold: Optional[str] = None,
                             alert_sms: Optional[bool] = None,
                             alert_email: Optional[bool] = None,
                             alert_whatsapp: Optional[bool] = None) -> Dict[str, Any]:
    """Update user preferences."""
    fields, vals = [], []
    if home_district is not None:
        fields.append("home_district=?"); vals.append(home_district)
    if home_state is not None:
        fields.append("home_state=?"); vals.append(home_state)
    if language is not None:
        fields.append("language=?"); vals.append(language)
    if alert_threshold is not None:
        fields.append("alert_threshold=?"); vals.append(alert_threshold)
    if alert_sms is not None:
        fields.append("alert_sms=?"); vals.append(int(alert_sms))
    if alert_email is not None:
        fields.append("alert_email=?"); vals.append(int(alert_email))
    if alert_whatsapp is not None:
        fields.append("alert_whatsapp=?"); vals.append(int(alert_whatsapp))

    if not fields:
        return get_user_by_id(db_path, user_id)

    vals.append(user_id)
    with _conn(db_path) as conn:
        conn.execute(
            f"UPDATE users SET {', '.join(fields)} WHERE id=?", vals)
    return get_user_by_id(db_path, user_id)


def logout_user(db_path: str, token: str) -> None:
    with _conn(db_path) as conn:
        conn.execute("DELETE FROM user_sessions WHERE token=?", (token,))


# ── Alert history ─────────────────────────────────────────────────────────────

def store_user_alert(db_path: str, user_id: int, alert_type: str,
                     message: str, severity: str,
                     district: Optional[str] = None,
                     channel: str = "system") -> int:
    with _conn(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO user_alerts
               (user_id, alert_type, district, message, severity, channel)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, alert_type, district, message, severity, channel)
        )
        return cur.lastrowid


def get_user_alert_history(db_path: str, user_id: int,
                            limit: int = 50) -> List[Dict[str, Any]]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM user_alerts WHERE user_id=?
               ORDER BY sent_at DESC LIMIT ?""",
            (user_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]


def acknowledge_alert(db_path: str, user_id: int, alert_id: int) -> bool:
    with _conn(db_path) as conn:
        cur = conn.execute(
            """UPDATE user_alerts SET is_read=1, acknowledged_at=?
               WHERE id=? AND user_id=?""",
            (datetime.now(timezone.utc).isoformat(), alert_id, user_id)
        )
        return cur.rowcount > 0


def get_unread_count(db_path: str, user_id: int) -> int:
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM user_alerts WHERE user_id=? AND is_read=0",
            (user_id,)
        ).fetchone()
        return row[0] if row else 0


# ── Notify matching users when an alert fires ──────────────────────────────────

def notify_users_for_alert(db_path: str, district: str,
                            alert_type: str, message: str,
                            severity: str) -> int:
    """
    Find all users whose home_district matches and whose threshold is met.
    Store an alert for each matching user.
    Returns count of users notified.
    """
    severity_rank = {"LOW": 1, "MODERATE": 2, "HIGH": 3, "CRITICAL": 4}
    alert_rank    = severity_rank.get(severity.upper(), 0)

    with _conn(db_path) as conn:
        users = conn.execute(
            """SELECT id, alert_threshold FROM users
               WHERE is_active=1
               AND (home_district=? OR home_district IS NULL)""",
            (district,)
        ).fetchall()

    count = 0
    for user in users:
        threshold_rank = severity_rank.get(user["alert_threshold"], 3)
        if alert_rank >= threshold_rank:
            store_user_alert(db_path, user["id"], alert_type,
                             message, severity, district, "system")
            count += 1

    log.info(f"Notified {count} users for {severity} alert in {district}")
    return count
