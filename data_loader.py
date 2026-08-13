"""
data_loader.py
--------------
Importa los datos de la hoja "All People" del Excel original hacia la base SQLite.

Reglas importantes:
- NUNCA se modifica el archivo Excel.
- La importación solo ocurre una vez: si un registro ya fue importado
  (identificado por su número de fila original), no se vuelve a insertar.
- Si el Excel cambia después, esto NO sobrescribe perfiles ya editados en la app.
- Los nombres de columnas se detectan de forma flexible, por si el Excel
  tiene pequeñas variaciones en los encabezados.
"""

import re
import pandas as pd

import database as db

EXCEL_PATH = "data/VC_Lab_C7_Introductions_v4.xlsx"
SHEET_NAME = "All People"

# Para cada campo interno, lista de posibles nombres de columna (normalizados) que lo representan.
# Se usa coincidencia flexible: se ignoran espacios, guiones, paréntesis y mayúsculas/minúsculas.
COLUMN_CANDIDATES = {
    "full_name": ["name", "fullname", "full name"],
    "geography": ["geography", "region", "location"],
    "category": ["category"],
    "discipline": ["discipline"],
    "primary_sector": ["sectorprimary", "primarysector", "sector1"],
    "secondary_sector": ["sectorsecondary", "secondarysector", "sector2"],
    "sub_category": ["subcategoryfocusarea", "subcategory", "focusarea"],
    "functional_expertise": ["functionalexpertise", "expertise"],
    "current_context": ["currentrolecontext", "currentrole", "context", "role"],
    "linkedin": ["linkedin", "linkedinprofile", "linkedinurl"],
}


def _normalize(col_name):
    """Convierte 'Sector (Primary)' -> 'sectorprimary' para comparar sin importar formato."""
    return re.sub(r"[^a-z0-9]", "", str(col_name).lower())


def detect_columns(df_columns):
    """
    Recorre las columnas reales del Excel y arma un mapeo:
    campo_interno -> nombre_real_de_columna
    Si no encuentra una columna para un campo, ese campo queda en None (se maneja con normalidad).
    """
    normalized_map = {_normalize(c): c for c in df_columns}
    mapping = {}
    for internal_field, candidates in COLUMN_CANDIDATES.items():
        found = None
        for candidate in candidates:
            if candidate in normalized_map:
                found = normalized_map[candidate]
                break
        mapping[internal_field] = found
    return mapping


def _clean_value(value):
    """Limpia valores tipo NaN, None o espacios en blanco provenientes del Excel."""
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def load_excel_dataframe():
    """Lee la hoja 'All People' del Excel y devuelve el DataFrame junto con el mapeo de columnas."""
    df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME)
    mapping = detect_columns(df.columns)
    return df, mapping


def import_initial_data():
    """
    Importa los registros del Excel hacia SQLite, solo si no fueron importados antes.
    Se identifica cada fila original por su índice (original_excel_row).
    Devuelve la cantidad de perfiles nuevos importados.
    """
    df, mapping = load_excel_dataframe()

    conn = db.get_connection()
    already_imported_rows = set(
        r["original_excel_row"]
        for r in conn.execute(
            "SELECT original_excel_row FROM profiles WHERE source = 'excel' AND original_excel_row IS NOT NULL"
        ).fetchall()
    )
    conn.close()

    imported_count = 0
    for idx, row in df.iterrows():
        if idx in already_imported_rows:
            continue  # ya fue importado antes, no se vuelve a insertar

        full_name = _clean_value(row.get(mapping.get("full_name"))) if mapping.get("full_name") else ""
        if not full_name:
            continue  # fila sin nombre, se ignora

        data = {
            "source": "excel",
            "original_excel_row": int(idx),
            "full_name": full_name,
            "email": "",
            "geography": _clean_value(row.get(mapping.get("geography"))) if mapping.get("geography") else "",
            "organization": "",  # el Excel original no separa organización, se completa luego en la app
            "current_role": "",  # idem, se completa luego en la app si el usuario lo desea
            "category": _clean_value(row.get(mapping.get("category"))) if mapping.get("category") else "",
            "discipline": _clean_value(row.get(mapping.get("discipline"))) if mapping.get("discipline") else "",
            "primary_sector": _clean_value(row.get(mapping.get("primary_sector"))) if mapping.get("primary_sector") else "",
            "secondary_sector": _clean_value(row.get(mapping.get("secondary_sector"))) if mapping.get("secondary_sector") else "",
            "sub_category": _clean_value(row.get(mapping.get("sub_category"))) if mapping.get("sub_category") else "",
            "functional_expertise": _clean_value(row.get(mapping.get("functional_expertise"))) if mapping.get("functional_expertise") else "",
            "current_context": _clean_value(row.get(mapping.get("current_context"))) if mapping.get("current_context") else "",
            "linkedin": _clean_value(row.get(mapping.get("linkedin"))) if mapping.get("linkedin") else "",
            "interests": "",
            "investment_thesis": "",
            "offering": "",
            "needs": "",
            "desired_connections": "",
            "consent": 0,
            "consent_date": None,
        }
        db.create_profile(data)
        imported_count += 1

    return imported_count


def ensure_data_loaded():
    """
    Se llama al inicio de la app.
    Crea la base si no existe y ejecuta la importación inicial (idempotente).
    """
    db.init_db()
    return import_initial_data()
