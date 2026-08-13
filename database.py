"""
database.py
------------
Todas las operaciones contra la base SQLite (vc_connection.db).

Este archivo NUNCA toca el Excel original. Solo lee/escribe en SQLite.

Tablas:
- profiles: perfiles de los participantes (importados del Excel o creados en la app)
- recommendations: conexiones recomendadas generadas por el motor de matching
- feedback: evaluaciones de utilidad de cada conexión
"""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "vc_connection.db"


def get_connection():
    """Abre una conexión a la base SQLite. Se debe cerrar (o usar 'with') después de usarla."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # permite acceder a columnas por nombre, ej: row["full_name"]
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """
    Crea las tablas si no existen todavía.
    Se puede llamar en cada arranque de la app sin problema (es idempotente).
    """
    conn = get_connection()
    cur = conn.cursor()

    # Tabla principal de perfiles
    cur.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,                 -- 'excel' o 'new'
            original_excel_row INTEGER,           -- fila original en el Excel (si aplica), para no reimportar
            full_name TEXT NOT NULL,
            email TEXT,
            geography TEXT,
            organization TEXT,
            current_role TEXT,
            category TEXT,
            discipline TEXT,
            primary_sector TEXT,
            secondary_sector TEXT,
            sub_category TEXT,                    -- columna extra del Excel: "Sub-Category (Focus Area)"
            functional_expertise TEXT,
            current_context TEXT,
            linkedin TEXT,
            interests TEXT,
            investment_thesis TEXT,
            offering TEXT,
            needs TEXT,
            desired_connections TEXT,
            consent INTEGER NOT NULL DEFAULT 0,   -- 0 = no, 1 = si
            consent_date TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Tabla de recomendaciones generadas
    cur.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_profile_id INTEGER NOT NULL,
            recommended_profile_id INTEGER NOT NULL,
            score REAL,
            thematic_score REAL,
            complementarity_score REAL,
            category_score REAL,
            reason TEXT,
            conversation_topics TEXT,             -- guardado como texto separado por "|"
            generated_at TEXT NOT NULL,
            FOREIGN KEY (user_profile_id) REFERENCES profiles(id),
            FOREIGN KEY (recommended_profile_id) REFERENCES profiles(id)
        )
    """)

    # Tabla de evaluaciones (feedback)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evaluator_profile_id INTEGER NOT NULL,
            evaluated_profile_id INTEGER NOT NULL,
            contacted TEXT,                       -- 'yes' o 'not_yet'
            usefulness_score INTEGER,             -- 1 a 5, solo si contacted = 'yes'
            result_type TEXT,
            comment TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (evaluator_profile_id) REFERENCES profiles(id),
            FOREIGN KEY (evaluated_profile_id) REFERENCES profiles(id)
        )
    """)

    conn.commit()
    conn.close()


def now_iso():
    """Fecha/hora actual en formato ISO, usada para created_at, updated_at, etc."""
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Funciones de búsqueda
# ---------------------------------------------------------------------------

def search_profiles_by_name(query, limit=8):
    """Busca perfiles cuyo nombre contenga el texto ingresado (búsqueda parcial, sin importar mayúsculas)."""
    if not query or not query.strip():
        return []
    conn = get_connection()
    like_query = f"%{query.strip()}%"
    rows = conn.execute(
        "SELECT * FROM profiles WHERE full_name LIKE ? COLLATE NOCASE ORDER BY full_name LIMIT ?",
        (like_query, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_profile_by_id(profile_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_profile_by_email(email):
    """Busca un perfil por correo exacto (normalizado en minúsculas). Ignora correos vacíos."""
    if not email or not email.strip():
        return None
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM profiles WHERE LOWER(email) = LOWER(?) AND TRIM(email) != ''",
        (email.strip(),),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def find_similar_profiles(full_name, email=None, exclude_id=None):
    """
    Control de duplicados al crear un perfil nuevo:
    busca coincidencias por nombre similar o por correo ya registrado.
    """
    conn = get_connection()
    name_norm = f"%{full_name.strip()}%"
    query = "SELECT * FROM profiles WHERE full_name LIKE ? COLLATE NOCASE"
    params = [name_norm]
    if exclude_id:
        query += " AND id != ?"
        params.append(exclude_id)
    by_name = conn.execute(query, params).fetchall()

    by_email = []
    if email and email.strip():
        query2 = "SELECT * FROM profiles WHERE LOWER(email) = LOWER(?) AND TRIM(email) != ''"
        params2 = [email.strip()]
        if exclude_id:
            query2 += " AND id != ?"
            params2.append(exclude_id)
        by_email = conn.execute(query2, params2).fetchall()

    conn.close()
    combined = {r["id"]: dict(r) for r in list(by_name) + list(by_email)}
    return list(combined.values())


# ---------------------------------------------------------------------------
# Funciones de creación / actualización de perfiles
# ---------------------------------------------------------------------------

PROFILE_FIELDS = [
    "source", "original_excel_row", "full_name", "email", "geography",
    "organization", "current_role", "category", "discipline",
    "primary_sector", "secondary_sector", "sub_category", "functional_expertise",
    "current_context", "linkedin", "interests", "investment_thesis",
    "offering", "needs", "desired_connections", "consent", "consent_date",
]


def create_profile(data: dict):
    """Crea un nuevo perfil. 'data' debe traer las llaves relevantes de PROFILE_FIELDS."""
    conn = get_connection()
    ts = now_iso()
    values = {field: data.get(field) for field in PROFILE_FIELDS}
    values["created_at"] = ts
    values["updated_at"] = ts

    columns = ", ".join(values.keys())
    placeholders = ", ".join(["?"] * len(values))
    cur = conn.execute(
        f"INSERT INTO profiles ({columns}) VALUES ({placeholders})",
        list(values.values()),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def update_profile(profile_id, data: dict):
    """Actualiza campos de un perfil existente. Solo actualiza las llaves presentes en 'data'."""
    if not data:
        return
    conn = get_connection()
    data = dict(data)
    data["updated_at"] = now_iso()
    set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
    values = list(data.values()) + [profile_id]
    conn.execute(f"UPDATE profiles SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_all_consenting_profiles(exclude_id=None):
    """
    Devuelve todos los perfiles que:
    - dieron consentimiento (consent = 1)
    - tienen correo
    Se usa como universo de candidatos para el matching.
    NUNCA se expone esta lista completa al usuario final (ver reglas de privacidad).
    """
    conn = get_connection()
    query = "SELECT * FROM profiles WHERE consent = 1 AND email IS NOT NULL AND TRIM(email) != ''"
    params = []
    if exclude_id:
        query += " AND id != ?"
        params.append(exclude_id)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Recomendaciones
# ---------------------------------------------------------------------------

def save_recommendations(user_profile_id, recommendations):
    """
    Guarda una nueva tanda de recomendaciones para un perfil.
    Reemplaza las anteriores (para no acumular recomendaciones viejas de sesiones pasadas).
    """
    conn = get_connection()
    ts = now_iso()
    conn.execute("DELETE FROM recommendations WHERE user_profile_id = ?", (user_profile_id,))
    for rec in recommendations:
        topics_str = "|".join(rec.get("conversation_topics", []))
        conn.execute(
            """INSERT INTO recommendations
               (user_profile_id, recommended_profile_id, score, thematic_score,
                complementarity_score, category_score, reason, conversation_topics, generated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_profile_id,
                rec["recommended_profile_id"],
                rec["score"],
                rec["thematic_score"],
                rec["complementarity_score"],
                rec["category_score"],
                rec["reason"],
                topics_str,
                ts,
            ),
        )
    conn.commit()
    conn.close()


def get_recommendations_for_profile(user_profile_id):
    """Devuelve las recomendaciones ya guardadas para un perfil, unidas con los datos del perfil recomendado."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT r.*, p.full_name, p.email, p.linkedin, p.organization, p.current_role,
                  p.current_context, p.geography, p.offering, p.needs
           FROM recommendations r
           JOIN profiles p ON p.id = r.recommended_profile_id
           WHERE r.user_profile_id = ?
           ORDER BY r.score DESC""",
        (user_profile_id,),
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["conversation_topics"] = d["conversation_topics"].split("|") if d["conversation_topics"] else []
        results.append(d)
    return results


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

def save_feedback(data: dict):
    conn = get_connection()
    conn.execute(
        """INSERT INTO feedback
           (evaluator_profile_id, evaluated_profile_id, contacted, usefulness_score,
            result_type, comment, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            data["evaluator_profile_id"],
            data["evaluated_profile_id"],
            data.get("contacted"),
            data.get("usefulness_score"),
            data.get("result_type"),
            data.get("comment"),
            now_iso(),
        ),
    )
    conn.commit()
    conn.close()


def get_feedback_given(evaluator_profile_id):
    """Devuelve las evaluaciones que un perfil ya hizo (para no mostrar el formulario dos veces)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM feedback WHERE evaluator_profile_id = ?", (evaluator_profile_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Exportación para el administrador
# ---------------------------------------------------------------------------

def get_all_profiles_df():
    import pandas as pd
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM profiles", conn)
    conn.close()
    return df


def get_all_feedback_df():
    import pandas as pd
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM feedback", conn)
    conn.close()
    return df
