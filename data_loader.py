"""Reads the source Excel file and imports the 'All People' sheet into SQLite.

The original Excel file is never modified. Column names are matched using
normalized aliases so small header variations do not break the import.
"""

import re

import pandas as pd

import database

EXCEL_PATH = "data/VC_Lab_C7_Introductions_v4.xlsx"
SHEET_NAME = "All People"

# Canonical internal field -> list of normalized header aliases to match.
COLUMN_ALIASES = {
    "full_name": ["name", "full name", "full_name"],
    "geography": ["geography", "region", "country"],
    "category": ["category"],
    "discipline": ["discipline"],
    "primary_sector": ["sector primary", "primary sector", "sector (primary)"],
    "secondary_sector": ["sector secondary", "secondary sector", "sector (secondary)"],
    "focus_area": [
        "sub category focus area",
        "sub-category (focus area)",
        "focus area",
        "sub category",
    ],
    "functional_expertise": ["functional expertise"],
    "current_context": [
        "current role context",
        "current role / context",
        "current role",
        "role context",
    ],
    "linkedin": ["linkedin", "linkedin profile", "linkedin url"],
}


def normalize_header(header):
    header = str(header).lower().strip()
    header = re.sub(r"[()/_-]", " ", header)
    header = re.sub(r"[^a-z0-9\s]", "", header)
    header = re.sub(r"\s+", " ", header).strip()
    return header


def detect_columns(columns):
    """Map each canonical field to the actual column name found in the sheet.

    First pass matches normalized aliases exactly. A second, looser pass
    only considers columns not already claimed by another field, and only
    matches on whole-word overlap (never a bare substring), so a short
    alias like "category" cannot hijack an unrelated multi-word column
    such as "Sub-Category (Focus Area)".
    """
    normalized_lookup = {normalize_header(col): col for col in columns}
    mapping = {}
    used_columns = set()

    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalized_lookup:
                original_col = normalized_lookup[alias]
                mapping[field] = original_col
                used_columns.add(original_col)
                break

    for field, aliases in COLUMN_ALIASES.items():
        if field in mapping:
            continue
        for norm_col, original_col in normalized_lookup.items():
            if original_col in used_columns:
                continue
            col_words = set(norm_col.split())
            matched = False
            for alias in aliases:
                alias_words = set(alias.split())
                if len(alias_words) < 2:
                    continue
                if alias_words <= col_words or col_words <= alias_words:
                    matched = True
                    break
            if matched:
                mapping[field] = original_col
                used_columns.add(original_col)
                break
    return mapping


def load_all_people(path=EXCEL_PATH, sheet_name=SHEET_NAME):
    """Read the source sheet and return a DataFrame with standardized columns
    plus the original row index (0-based, matching the Excel data rows)."""
    df = pd.read_excel(path, sheet_name=sheet_name)
    column_map = detect_columns(df.columns)

    standardized = pd.DataFrame()
    for field in COLUMN_ALIASES:
        source_col = column_map.get(field)
        if source_col is not None:
            standardized[field] = df[source_col].astype(str).replace("nan", "").str.strip()
        else:
            standardized[field] = ""

    standardized["original_excel_row"] = df.index

    # Fold the focus area into current_context so no information is lost,
    # since it is not part of the core profile schema.
    def merge_focus(row):
        context = row["current_context"]
        focus = row["focus_area"]
        if focus and focus.lower() not in context.lower():
            return f"{context} (Focus: {focus})" if context else f"Focus: {focus}"
        return context

    standardized["current_context"] = standardized.apply(merge_focus, axis=1)
    standardized = standardized.drop(columns=["focus_area"])

    # Drop rows without a usable name.
    standardized = standardized[standardized["full_name"].str.strip() != ""]
    return standardized


def import_new_records():
    """Import any 'All People' rows not yet present in the profiles table.

    Existing profiles (created or edited from the app) are never touched.
    """
    database.init_db()
    already_imported = database.get_all_excel_row_ids()
    df = load_all_people()

    new_records = []
    for _, row in df.iterrows():
        excel_row = int(row["original_excel_row"])
        if excel_row in already_imported:
            continue
        new_records.append(
            {
                "original_excel_row": excel_row,
                "full_name": row["full_name"],
                "email": None,
                "geography": row["geography"],
                "organization": "",
                "current_role": "",
                "category": row["category"],
                "discipline": row["discipline"],
                "primary_sector": row["primary_sector"],
                "secondary_sector": row["secondary_sector"],
                "functional_expertise": row["functional_expertise"],
                "current_context": row["current_context"],
                "linkedin": row["linkedin"],
                "interests": "",
                "investment_thesis": "",
                "offering": "",
                "needs": "",
                "desired_connections": "",
            }
        )

    database.bulk_insert_excel_profiles(new_records)
    return len(new_records)
