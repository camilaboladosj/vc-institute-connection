"""Rule-based explanations for each match. No external AI is used.

Every sentence is built directly from the two profiles' own data, so the
explanation never states anything that is not actually in the records.
"""

import re

STOPWORDS = {
    "and", "or", "the", "a", "an", "of", "in", "for", "to", "with", "on",
    "y", "de", "la", "el", "en", "para", "con", "un", "una", "los", "las",
}


def _split_terms(text):
    if not text:
        return []
    parts = re.split(r"[,;/]|\band\b|\by\b", text, flags=re.IGNORECASE)
    terms = []
    for part in parts:
        term = part.strip(" .").lower()
        if term and term not in STOPWORDS and len(term) > 2:
            terms.append(term)
    return terms


def _shared_terms(text_a, text_b, limit=3):
    terms_a = _split_terms(text_a)
    terms_b = set(_split_terms(text_b))
    shared = []
    for term in terms_a:
        if term in terms_b and term not in shared:
            shared.append(term)
        if len(shared) >= limit:
            break
    return shared


def _truncate(text, max_len=90):
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0] + "..."


def build_explanation(user_profile, candidate_profile):
    """Return (reason_text, conversation_topics list) for this match."""
    sentences = []
    topics = []

    # 1. Shared interests.
    shared_interests = _shared_terms(
        user_profile.get("interests", ""), candidate_profile.get("interests", "")
    )
    if shared_interests:
        sentences.append(
            "You both share an interest in " + ", ".join(shared_interests) + "."
        )
        topics.extend(shared_interests)

    # 2. Shared primary sector.
    sector_a = (user_profile.get("primary_sector") or "").strip()
    sector_b = (candidate_profile.get("primary_sector") or "").strip()
    if sector_a and sector_b and sector_a.lower() == sector_b.lower():
        sentences.append(f"You are both active in {sector_a}.")
        if sector_a.lower() not in [t.lower() for t in topics]:
            topics.append(sector_a)

    # 3. Shared discipline.
    discipline_a = (user_profile.get("discipline") or "").strip()
    discipline_b = (candidate_profile.get("discipline") or "").strip()
    if discipline_a and discipline_b and discipline_a.lower() == discipline_b.lower():
        sentences.append(f"You share a background in {discipline_a}.")

    # 4. Complementarity: what the candidate needs vs. what the user offers.
    candidate_needs = candidate_profile.get("needs", "")
    user_offering = user_profile.get("offering", "")
    if candidate_needs and user_offering:
        name = candidate_profile.get("full_name", "This person")
        sentences.append(
            f"{name} is looking for {_truncate(candidate_needs)}, "
            f"and you can offer {_truncate(user_offering)}."
        )

    # 5. Complementarity: what the user needs vs. what the candidate offers.
    user_needs = user_profile.get("needs", "")
    candidate_offering = candidate_profile.get("offering", "")
    if user_needs and candidate_offering:
        sentences.append(
            f"You are looking for {_truncate(user_needs)}, and they can offer "
            f"{_truncate(candidate_offering)}."
        )

    if not sentences:
        sentences.append(
            "Your profiles were matched based on overall thematic similarity."
        )

    if not topics:
        # Fall back to sector/discipline if no shared interest terms were found.
        for value in [sector_a, discipline_a]:
            if value and value not in topics:
                topics.append(value)

    reason = " ".join(sentences[:3])
    return reason, topics[:3]
