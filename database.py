"""SQLite database layer for VC Institute Connection.

Handles schema creation and all read/write access to profiles,
recommendations, and feedback. SQLite ships with Python, so no extra
dependency is required.
"""

import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_PATH = "vc_connection.db"

PROFILE_COLUMNS = [
    "source",
    "original_excel_row",
    "full_name",
    "email",
    "geography",
    "organization",
    "current_role",
    "category",
    "discipline",
    "primary_sector",
    "secondary_sector",
    "functional_expertise",
    "current_context",
    "linkedin",
    "interests",
    "investment_thesis",
    "offering",
    "needs",
    "desired_connections",
    "consent",
    "consent_date",
    "created_at",
    "updated_at",
]


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def normalize_text(value):
    """Lowercase, trim, and collapse whitespace for comparison purposes."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def normalize_email(value):
    return normalize_text(value)


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create tables if they do not already exist."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL DEFAULT 'new',
                original_excel_row INTEGER,
                full_name TEXT NOT NULL,
                email TEXT,
                geography TEXT,
                organization TEXT,
                current_role TEXT,
                category TEXT,
                discipline TEXT,
                primary_sector TEXT,
                secondary_sector TEXT,
                functional_expertise TEXT,
                current_context TEXT,
                linkedin TEXT,
                interests TEXT,
                investment_thesis TEXT,
                offering TEXT,
                needs TEXT,
                desired_connections TEXT,
                consent INTEGER NOT NULL DEFAULT 0,
                consent_date TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_profiles_email
            ON profiles(email) WHERE email IS NOT NULL AND email != ''
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_profile_id INTEGER NOT NULL,
                recommended_profile_id INTEGER NOT NULL,
                score REAL,
                thematic_score REAL,
                complementarity_score REAL,
                category_score REAL,
                reason TEXT,
                conversation_topics TEXT,
                generated_at TEXT NOT NULL,
                FOREIGN KEY(user_profile_id) REFERENCES profiles(id),
                FOREIGN KEY(recommended_profile_id) REFERENCES profiles(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluator_profile_id INTEGER NOT NULL,
                evaluated_profile_id INTEGER NOT NULL,
                contacted TEXT NOT NULL,
                usefulness_score INTEGER,
                result_type TEXT,
                comment TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(evaluator_profile_id) REFERENCES profiles(id),
                FOREIGN KEY(evaluated_profile_id) REFERENCES profiles(id)
            )
            """
        )


def search_profiles_by_name(query, limit=15):
    """Return lightweight matches (id, name, geography, org) for the search box."""
    query = query.strip()
    if not query:
        return []
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, full_name, geography, organization, current_context
            FROM profiles
            WHERE full_name LIKE ?
            ORDER BY full_name
            LIMIT ?
            """,
            (f"%{query}%", limit),
        ).fetchall()
        return [dict(row) for row in rows]


def get_profile(profile_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM profiles WHERE id = ?", (profile_id,)
        ).fetchone()
        return dict(row) if row else None


def find_by_email(email):
    email_norm = normalize_email(email)
    if not email_norm:
        return None
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM profiles WHERE LOWER(TRIM(email)) = ?", (email_norm,)
        ).fetchone()
        return dict(row) if row else None


def find_similar_by_name(full_name, limit=5):
    name_norm = normalize_text(full_name)
    if not name_norm:
        return []
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, full_name, email FROM profiles WHERE LOWER(TRIM(full_name)) LIKE ? LIMIT ?",
            (f"%{name_norm}%", limit),
        ).fetchall()
        return [dict(row) for row in rows]


def create_profile(fields):
    """Insert a new profile. Returns the new profile id.

    Raises ValueError if the email is already registered.
    """
    email = fields.get("email")
    if email and find_by_email(email):
        raise ValueError("This email is already registered to a profile.")

    data = {col: fields.get(col) for col in PROFILE_COLUMNS}
    data.setdefault("source", "new")
    data.setdefault("consent", 0)
    timestamp = now_iso()
    data["created_at"] = timestamp
    data["updated_at"] = timestamp

    columns = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    with get_connection() as conn:
        cursor = conn.execute(
            f"INSERT INTO profiles ({columns}) VALUES ({placeholders})",
            list(data.values()),
        )
        return cursor.lastrowid


def update_profile(profile_id, fields):
    """Update an existing profile with the given field values."""
    email = fields.get("email")
    if email:
        existing = find_by_email(email)
        if existing and existing["id"] != profile_id:
            raise ValueError("This email is already registered to another profile.")

    fields = dict(fields)
    fields["updated_at"] = now_iso()
    columns = ", ".join(f"{col} = ?" for col in fields.keys())
    with get_connection() as conn:
        conn.execute(
            f"UPDATE profiles SET {columns} WHERE id = ?",
            list(fields.values()) + [profile_id],
        )


def get_all_excel_row_ids():
    """Return the set of original_excel_row values already imported."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT original_excel_row FROM profiles WHERE source = 'excel' "
            "AND original_excel_row IS NOT NULL"
        ).fetchall()
        return {row["original_excel_row"] for row in rows}


def bulk_insert_excel_profiles(records):
    """Insert multiple Excel-sourced profiles that have not been imported yet."""
    if not records:
        return
    timestamp = now_iso()
    with get_connection() as conn:
        for record in records:
            data = {col: record.get(col) for col in PROFILE_COLUMNS}
            data["source"] = "excel"
            data["consent"] = 0
            data["created_at"] = timestamp
            data["updated_at"] = timestamp
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            conn.execute(
                f"INSERT INTO profiles ({columns}) VALUES ({placeholders})",
                list(data.values()),
            )


def get_eligible_profiles_for_matching(exclude_id=None):
    """Return profiles eligible to be recommended: consented, with email, complete enough."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM profiles WHERE consent = 1").fetchall()
    profiles = [dict(row) for row in rows]
    eligible = []
    seen_emails = set()
    for profile in profiles:
        if exclude_id is not None and profile["id"] == exclude_id:
            continue
        email = normalize_email(profile.get("email"))
        if not email:
            continue
        if email in seen_emails:
            continue
        if not is_profile_complete(profile):
            continue
        seen_emails.add(email)
        eligible.append(profile)
    return eligible


def is_profile_complete(profile):
    """A profile is complete enough for matching if it has a name, email,
    and at least the core matching fields filled in."""
    required = ["full_name", "email", "interests", "offering", "needs"]
    return all((profile.get(field) or "").strip() for field in required)


def save_recommendations(user_profile_id, recommendations):
    """Replace stored recommendations for a user with a fresh set."""
    timestamp = now_iso()
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM recommendations WHERE user_profile_id = ?", (user_profile_id,)
        )
        for rec in recommendations:
            conn.execute(
                """
                INSERT INTO recommendations (
                    user_profile_id, recommended_profile_id, score,
                    thematic_score, complementarity_score, category_score,
                    reason, conversation_topics, generated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_profile_id,
                    rec["profile_id"],
                    rec["score"],
                    rec["thematic_score"],
                    rec["complementarity_score"],
                    rec["category_score"],
                    rec["reason"],
                    " | ".join(rec["conversation_topics"]),
                    timestamp,
                ),
            )


def get_recommendations_for_user(user_profile_id):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT r.*, p.full_name, p.email, p.linkedin, p.organization,
                   p.current_role, p.geography, p.offering, p.needs
            FROM recommendations r
            JOIN profiles p ON p.id = r.recommended_profile_id
            WHERE r.user_profile_id = ?
            ORDER BY r.score DESC
            """,
            (user_profile_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def save_feedback(fields):
    fields = dict(fields)
    fields["created_at"] = now_iso()
    columns = ", ".join(fields.keys())
    placeholders = ", ".join(["?"] * len(fields))
    with get_connection() as conn:
        conn.execute(
            f"INSERT INTO feedback ({columns}) VALUES ({placeholders})",
            list(fields.values()),
        )


def get_all_profiles_df():
    import pandas as pd

    with get_connection() as conn:
        return pd.read_sql_query("SELECT * FROM profiles", conn)


def get_all_feedback_df():
    import pandas as pd

    with get_connection() as conn:
        return pd.read_sql_query("SELECT * FROM feedback", conn)
