"""
explanations.py
----------------
Genera explicaciones de match usando reglas simples (sin IA externa).

Todo el texto generado aquí es el que verá el usuario final, por lo tanto
está en ingles, tal como pide la especificacion del proyecto.
"""

import re

# Palabras muy comunes en ingles que se ignoran al comparar intereses (stopwords basicas)
STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "about",
    "your", "you", "are", "our", "their", "have", "has", "will", "can",
    "not", "but", "all", "any", "who", "what", "how", "when", "where",
    "a", "an", "of", "in", "on", "to", "is", "it", "as", "at", "be", "or",
}


def _keywords(text, min_len=4):
    """Extrae palabras significativas (sin stopwords) de un texto, en minusculas y sin duplicados."""
    if not text:
        return []
    words = re.findall(r"[a-zA-Z]+", text.lower())
    seen = []
    for w in words:
        if len(w) >= min_len and w not in STOPWORDS and w not in seen:
            seen.append(w)
    return seen


def _common_keywords(text_a, text_b, limit=3):
    """Devuelve hasta 'limit' palabras que aparecen en ambos textos."""
    words_a = _keywords(text_a)
    words_b = set(_keywords(text_b))
    common = [w for w in words_a if w in words_b]
    return common[:limit]


def generate_reason(profile_a, profile_b, scores):
    """
    Construye una explicacion breve y natural del match, usando solo datos reales.
    profile_a = el usuario que esta viendo las recomendaciones.
    profile_b = la persona recomendada.
    """
    name_b = profile_b.get("full_name", "This person")
    sentences = []

    # 1. Coincidencia de sector
    sector_a = (profile_a.get("primary_sector") or "").strip()
    sector_b = (profile_b.get("primary_sector") or "").strip()
    if sector_a and sector_b and sector_a.lower() == sector_b.lower():
        sentences.append(f"You both focus on {sector_a}.")

    # 2. Complementariedad: lo que A busca y lo que B ofrece (y viceversa)
    common_need_offer = _common_keywords(profile_a.get("needs"), profile_b.get("offering"))
    if common_need_offer:
        sentences.append(
            f"{name_b} can offer something close to what you are looking for, "
            f"particularly around {', '.join(common_need_offer)}."
        )
    else:
        common_offer_need = _common_keywords(profile_a.get("offering"), profile_b.get("needs"))
        if common_offer_need:
            sentences.append(
                f"What you can offer aligns with what {name_b} is looking for, "
                f"particularly around {', '.join(common_offer_need)}."
            )

    # 3. Intereses en comun
    common_interests = _common_keywords(profile_a.get("interests"), profile_b.get("interests"))
    if common_interests:
        sentences.append(f"You share an interest in {', '.join(common_interests)}.")

    # 4. Disciplinas diferentes pero sector en comun (complementariedad por area)
    disc_a = (profile_a.get("discipline") or "").strip()
    disc_b = (profile_b.get("discipline") or "").strip()
    if disc_a and disc_b and disc_a.lower() != disc_b.lower() and sector_a and sector_b and sector_a.lower() == sector_b.lower():
        sentences.append(f"Your backgrounds are complementary: {disc_a} and {disc_b}.")

    if not sentences:
        sentences.append(
            f"Your profile and {name_b}'s profile show related interests worth exploring in conversation."
        )

    return " ".join(sentences)


def generate_topics(profile_a, profile_b, limit=3):
    """
    Genera hasta 'limit' temas sugeridos para iniciar la conversacion,
    a partir de palabras clave compartidas en intereses y tesis de inversion.
    """
    text_a = " ".join([profile_a.get("interests") or "", profile_a.get("investment_thesis") or ""])
    text_b = " ".join([profile_b.get("interests") or "", profile_b.get("investment_thesis") or ""])

    common = _common_keywords(text_a, text_b, limit=limit)
    topics = [w.capitalize() for w in common]

    # Si no hay suficientes palabras en comun, se completa con el sector compartido
    if len(topics) < limit:
        sector_a = (profile_a.get("primary_sector") or "").strip()
        sector_b = (profile_b.get("primary_sector") or "").strip()
        if sector_a and sector_a.lower() == (sector_b or "").lower() and sector_a not in topics:
            topics.append(sector_a)

    return topics[:limit] if topics else ["General introduction"]
