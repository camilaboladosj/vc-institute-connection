"""Simple, transparent matching engine.

Combines thematic similarity (interests, thesis, sector, discipline,
functional expertise, current context) with complementarity (what one
person needs versus what the other offers), plus a small bonus for
matching structured categories. All similarity is computed with TF-IDF
and cosine similarity from scikit-learn. No external models are used.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import database

THEMATIC_WEIGHT = 0.40
COMPLEMENTARITY_WEIGHT = 0.45
CATEGORY_WEIGHT = 0.15

CATEGORY_FIELDS = ["primary_sector", "discipline", "functional_expertise"]

MAX_RECOMMENDATIONS = 5


def _text(*parts):
    return " ".join(p.strip() for p in parts if p and p.strip())


def _thematic_text(profile):
    return _text(
        profile.get("interests", ""),
        profile.get("investment_thesis", ""),
        profile.get("primary_sector", ""),
        profile.get("secondary_sector", ""),
        profile.get("discipline", ""),
        profile.get("functional_expertise", ""),
        profile.get("current_context", ""),
    )


def _category_score(profile_a, profile_b):
    matches = 0
    for field in CATEGORY_FIELDS:
        value_a = (profile_a.get(field) or "").strip().lower()
        value_b = (profile_b.get(field) or "").strip().lower()
        if value_a and value_b and value_a == value_b:
            matches += 1
    return (matches / len(CATEGORY_FIELDS)) * 100


def generate_recommendations(user_profile):
    """Return up to MAX_RECOMMENDATIONS scored candidates for user_profile.

    Each result is a dict with profile_id, score, thematic_score,
    complementarity_score, category_score, reason, conversation_topics.
    """
    candidates = database.get_eligible_profiles_for_matching(exclude_id=user_profile["id"])
    if not candidates:
        return []

    all_profiles = [user_profile] + candidates
    user_index = 0

    thematic_texts = [_thematic_text(p) or "no information" for p in all_profiles]
    thematic_vectorizer = TfidfVectorizer(stop_words="english")
    thematic_matrix = thematic_vectorizer.fit_transform(thematic_texts)
    thematic_sim = cosine_similarity(thematic_matrix[user_index], thematic_matrix).flatten()

    needs_texts = [(p.get("needs") or "no information") for p in all_profiles]
    offering_texts = [(p.get("offering") or "no information") for p in all_profiles]
    comp_vectorizer = TfidfVectorizer(stop_words="english")
    comp_vectorizer.fit(needs_texts + offering_texts)
    needs_matrix = comp_vectorizer.transform(needs_texts)
    offering_matrix = comp_vectorizer.transform(offering_texts)

    # A's needs vs B's offering, and B's needs vs A's offering.
    user_needs_vs_all_offering = cosine_similarity(needs_matrix[user_index], offering_matrix).flatten()
    all_needs_vs_user_offering = cosine_similarity(offering_matrix[user_index], needs_matrix).flatten()

    results = []
    for i, candidate in enumerate(candidates):
        idx = i + 1  # offset for user at position 0
        thematic_score = float(thematic_sim[idx]) * 100
        complementarity_score = (
            (user_needs_vs_all_offering[idx] + all_needs_vs_user_offering[idx]) / 2
        ) * 100
        category_score = _category_score(user_profile, candidate)

        final_score = (
            THEMATIC_WEIGHT * thematic_score
            + COMPLEMENTARITY_WEIGHT * complementarity_score
            + CATEGORY_WEIGHT * category_score
        )
        final_score = max(0.0, min(100.0, final_score))

        results.append(
            {
                "profile_id": candidate["id"],
                "profile": candidate,
                "score": round(final_score, 1),
                "thematic_score": round(thematic_score, 1),
                "complementarity_score": round(complementarity_score, 1),
                "category_score": round(category_score, 1),
            }
        )

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:MAX_RECOMMENDATIONS]
