"""
matching.py
-----------
Motor de matching simple y explicable. No usa modelos de IA externos.

Combina:
A) Similitud temática (intereses, tesis, sector, disciplina, expertise, contexto) - 40%
B) Complementariedad entre lo que busca uno y lo que ofrece el otro - 45%
C) Coincidencia de categorías estructuradas (sector, disciplina, expertise) - 15%

Puntuación final normalizada de 0 a 100.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import database as db
import explanations

WEIGHT_THEMATIC = 0.40
WEIGHT_COMPLEMENTARITY = 0.45
WEIGHT_CATEGORY = 0.15

MAX_RECOMMENDATIONS = 5

# Un perfil se considera "demasiado incompleto" para el matching si no tiene
# texto suficiente en estos campos combinados.
MIN_TEXT_LENGTH = 10


def _thematic_text(profile):
    """Concatena los campos usados para medir similitud temática."""
    parts = [
        profile.get("interests") or "",
        profile.get("investment_thesis") or "",
        profile.get("primary_sector") or "",
        profile.get("secondary_sector") or "",
        profile.get("discipline") or "",
        profile.get("functional_expertise") or "",
        profile.get("current_context") or "",
    ]
    return " ".join(p for p in parts if p).strip()


def _is_profile_complete_enough(profile):
    """Un perfil necesita al menos intereses, oferta o necesidad con contenido real."""
    combined = " ".join([
        profile.get("interests") or "",
        profile.get("offering") or "",
        profile.get("needs") or "",
    ])
    return len(combined.strip()) >= MIN_TEXT_LENGTH


def _safe_cosine(text_a, text_b):
    """
    Calcula similitud coseno TF-IDF entre dos textos.
    Si algún texto está vacío, devuelve 0 (no se puede comparar).
    """
    text_a = (text_a or "").strip()
    text_b = (text_b or "").strip()
    if not text_a or not text_b:
        return 0.0
    try:
        vectorizer = TfidfVectorizer(stop_words="english")
        matrix = vectorizer.fit_transform([text_a, text_b])
        sim = cosine_similarity(matrix[0:1], matrix[1:2])[0][0]
        return float(sim)
    except ValueError:
        # Puede pasar si el texto solo tiene stopwords o quedó vacío tras vectorizar
        return 0.0


def _category_score(profile_a, profile_b):
    """
    Puntuación de coincidencia de categorías estructuradas (0 a 1).
    Compara sector primario, disciplina y expertise funcional de forma exacta (insensible a mayúsculas).
    """
    fields = ["primary_sector", "discipline", "functional_expertise"]
    matches = 0
    comparable = 0
    for field in fields:
        val_a = (profile_a.get(field) or "").strip().lower()
        val_b = (profile_b.get(field) or "").strip().lower()
        if val_a and val_b:
            comparable += 1
            if val_a == val_b:
                matches += 1
    if comparable == 0:
        return 0.0
    return matches / comparable


def compute_match(profile_a, profile_b):
    """
    Calcula los tres componentes del score y el score final (0-100) entre dos perfiles.
    Devuelve un diccionario con los detalles.
    """
    thematic = _safe_cosine(_thematic_text(profile_a), _thematic_text(profile_b))

    # Complementariedad: lo que A busca vs lo que B ofrece, y viceversa. Se promedian.
    comp_a_to_b = _safe_cosine(profile_a.get("needs"), profile_b.get("offering"))
    comp_b_to_a = _safe_cosine(profile_b.get("needs"), profile_a.get("offering"))
    complementarity = (comp_a_to_b + comp_b_to_a) / 2

    category = _category_score(profile_a, profile_b)

    final_score = (
        WEIGHT_THEMATIC * thematic
        + WEIGHT_COMPLEMENTARITY * complementarity
        + WEIGHT_CATEGORY * category
    )
    final_score_normalized = round(final_score * 100, 1)

    return {
        "score": final_score_normalized,
        "thematic_score": round(thematic * 100, 1),
        "complementarity_score": round(complementarity * 100, 1),
        "category_score": round(category * 100, 1),
    }


def generate_recommendations(profile):
    """
    Genera hasta MAX_RECOMMENDATIONS recomendaciones para un perfil dado.
    Excluye: el propio perfil, perfiles sin consentimiento, sin correo, y perfiles muy incompletos.
    Devuelve una lista lista para guardar con database.save_recommendations().
    """
    candidates = db.get_all_consenting_profiles(exclude_id=profile["id"])

    scored = []
    for candidate in candidates:
        if not _is_profile_complete_enough(candidate):
            continue
        result = compute_match(profile, candidate)
        reason = explanations.generate_reason(profile, candidate, result)
        topics = explanations.generate_topics(profile, candidate)
        scored.append({
            "recommended_profile_id": candidate["id"],
            "score": result["score"],
            "thematic_score": result["thematic_score"],
            "complementarity_score": result["complementarity_score"],
            "category_score": result["category_score"],
            "reason": reason,
            "conversation_topics": topics,
        })

    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:MAX_RECOMMENDATIONS]
