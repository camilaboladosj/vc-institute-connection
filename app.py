"""
app.py
------
Aplicación principal de VC INSTITUTE CONNECTION.

Flujo (guardado en st.session_state["stage"]):
  search        -> buscar perfil por nombre o crear uno nuevo
  profile_form  -> revisar/editar perfil existente o crear uno nuevo + completar campos de matching
  consent       -> aceptar (o no) compartir los datos
  connections   -> ver hasta 5 conexiones recomendadas
  feedback      -> evaluar si las conexiones fueron utiles

Todo el texto visible para el usuario esta en ingles, tal como pide la especificacion.
Los comentarios del codigo estan en español para que sea mas facil de entender y mantener.
"""

import urllib.parse

import streamlit as st

import database as db
import data_loader
import matching

# ---------------------------------------------------------------------------
# Configuracion general de la pagina
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="VC INSTITUTE CONNECTION",
    page_icon=None,
    layout="centered",  # una sola columna, mas facil de usar desde el telefono
)

# Colores neutros, azul oscuro como color principal. Diseño sobrio, sin animaciones.
st.markdown(
    """
    <style>
        .stButton > button {
            width: 100%;
            border-radius: 6px;
            padding: 0.6rem 1rem;
            font-weight: 600;
        }
        div[data-testid="stForm"] button {
            background-color: #10265e;
            color: white;
        }
        .match-card {
            border: 1px solid #d7dce3;
            border-radius: 10px;
            padding: 1.1rem 1.2rem;
            margin-bottom: 1.2rem;
            background-color: #f7f9fc;
        }
        .match-score {
            color: #10265e;
            font-weight: 700;
            font-size: 1.05rem;
        }
        h1 {
            color: #10265e;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Inicializacion (se ejecuta una sola vez por sesion de servidor gracias a cache)
# ---------------------------------------------------------------------------

@st.cache_resource
def _initialize_database_once():
    """Crea la base SQLite (si no existe) e importa los datos del Excel (si no fueron importados)."""
    return data_loader.ensure_data_loaded()


_initialize_database_once()

# Valores por defecto de session_state
DEFAULTS = {
    "stage": "search",
    "profile_id": None,
    "is_new_profile": False,
    "search_query": "",
    "duplicate_warning_shown": False,
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ---------------------------------------------------------------------------
# Barra de progreso simple
# ---------------------------------------------------------------------------

STAGE_ORDER = ["search", "profile_form", "consent", "connections", "feedback"]
STAGE_LABELS = {
    "search": "1. Profile",
    "profile_form": "2. Interests",
    "consent": "3. Consent",
    "connections": "4. Connections",
    "feedback": "5. Feedback",
}


def render_progress():
    current_index = STAGE_ORDER.index(st.session_state["stage"])
    cols = st.columns(len(STAGE_ORDER))
    for i, key in enumerate(STAGE_ORDER):
        with cols[i]:
            if i < current_index:
                st.markdown("<div style='text-align:center; color:#10265e;'>✓</div>", unsafe_allow_html=True)
            elif i == current_index:
                st.markdown("<div style='text-align:center; color:#10265e; font-weight:700;'>●</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div style='text-align:center; color:#c3c9d3;'>○</div>", unsafe_allow_html=True)
            st.caption(STAGE_LABELS[key].split(". ")[1])
    st.progress(current_index / (len(STAGE_ORDER) - 1))


def go_to(stage):
    st.session_state["stage"] = stage
    st.rerun()


# ---------------------------------------------------------------------------
# STAGE: search
# ---------------------------------------------------------------------------

def render_search_stage():
    st.title("VC INSTITUTE CONNECTION")
    st.write("Find people in the cohort worth connecting with.")

    st.subheader("Find your profile")
    query = st.text_input("Search your profile by name", value=st.session_state["search_query"])
    st.session_state["search_query"] = query

    if query.strip():
        matches = db.search_profiles_by_name(query)
        if matches:
            st.write("Select your name:")
            for m in matches:
                if st.button(m["full_name"], key=f"match_{m['id']}"):
                    st.session_state["profile_id"] = m["id"]
                    st.session_state["is_new_profile"] = False
                    go_to("profile_form")
        else:
            st.info("No matches found. You can create a new profile below.")

    st.divider()
    st.write("Not in the database?")
    if st.button("Create a profile"):
        st.session_state["profile_id"] = None
        st.session_state["is_new_profile"] = True
        st.session_state["duplicate_warning_shown"] = False
        go_to("profile_form")


# ---------------------------------------------------------------------------
# STAGE: profile_form (revisar/editar existente, o crear nuevo) + campos de matching
# ---------------------------------------------------------------------------

def render_profile_form_stage():
    is_new = st.session_state["is_new_profile"]
    existing = None
    if not is_new and st.session_state["profile_id"]:
        existing = db.get_profile_by_id(st.session_state["profile_id"])

    if existing:
        st.subheader("Review your information")
        st.write("We found your profile. Review the information, add your email, and complete your interests.")
    else:
        st.subheader("Create a profile")
        st.write("Fill in your basic information to join VC Institute Connection.")

    existing = existing or {}

    if st.button("← Back to search"):
        st.session_state["duplicate_warning_shown"] = False
        go_to("search")

    with st.form("profile_form", clear_on_submit=False):
        full_name = st.text_input("Full name", value=existing.get("full_name", ""))
        email = st.text_input("Email address", value=existing.get("email", ""))

        st.markdown("**Basic information**")
        geography = st.text_input("Geography / country / region", value=existing.get("geography", ""))
        organization = st.text_input("Organization or company", value=existing.get("organization", ""))
        current_role_field = st.text_input(
            "Current role / professional context",
            value=existing.get("current_role") or existing.get("current_context") or "",
        )
        category = st.text_input("Category", value=existing.get("category", ""))
        discipline = st.text_input("Discipline", value=existing.get("discipline", ""))
        primary_sector = st.text_input("Sector (Primary)", value=existing.get("primary_sector", ""))
        secondary_sector = st.text_input("Sector (Secondary)", value=existing.get("secondary_sector", ""))
        sub_category = st.text_input("Sub-Category (Focus Area)", value=existing.get("sub_category", ""))
        functional_expertise = st.text_input("Functional Expertise", value=existing.get("functional_expertise", ""))
        linkedin = st.text_input("LinkedIn (optional)", value=existing.get("linkedin", ""))

        st.markdown("---")
        st.subheader("Complete your connection profile")

        interests = st.text_area(
            "What are your main areas of interest?",
            value=existing.get("interests", ""),
            placeholder="Fintech, impact investing, artificial intelligence, and startup development.",
        )
        investment_thesis = st.text_area(
            "What are you currently working on, or what is your investment thesis?",
            value=existing.get("investment_thesis", ""),
        )
        offering = st.text_area(
            "What can you offer other members of the cohort?",
            value=existing.get("offering", ""),
            placeholder="Experience in project evaluation, public innovation, and ecosystem building.",
        )
        needs = st.text_area(
            "What are you looking for within the cohort?",
            value=existing.get("needs", ""),
            placeholder="Meeting impact investors and people with experience in creative-industry funds.",
        )
        desired_connections = st.text_area(
            "What type of people would you like to connect with?",
            value=existing.get("desired_connections", ""),
        )

        submitted = st.form_submit_button("Save and continue")

    if not submitted:
        return

    # Validacion basica
    errors = []
    if not full_name.strip():
        errors.append("Full name is required.")
    if not email.strip() or "@" not in email:
        errors.append("A valid email address is required.")

    if errors:
        for e in errors:
            st.error(e)
        return

    # Control de duplicados de correo (excluyendo el propio perfil si ya existe)
    exclude_id = existing.get("id") if existing else None
    email_owner = db.get_profile_by_email(email)
    if email_owner and email_owner["id"] != exclude_id:
        st.error(
            f"This email is already registered under the name '{email_owner['full_name']}'. "
            f"Please search for that profile instead, or use a different email."
        )
        return

    # Si es un perfil nuevo, avisar (una sola vez) si hay perfiles con nombre parecido (posible duplicado)
    if is_new and not st.session_state["duplicate_warning_shown"]:
        similar = db.find_similar_profiles(full_name, email)
        if similar:
            st.warning(
                "We found a similar profile already in the database: "
                + ", ".join(s["full_name"] for s in similar)
                + ". If this is you, go back and search for your name instead. "
                + "Otherwise, click 'Save and continue' again to create this profile anyway."
            )
            st.session_state["duplicate_warning_shown"] = True
            return

    data = {
        "full_name": full_name.strip(),
        "email": email.strip().lower(),
        "geography": geography.strip(),
        "organization": organization.strip(),
        "current_role": current_role_field.strip(),
        "category": category.strip(),
        "discipline": discipline.strip(),
        "primary_sector": primary_sector.strip(),
        "secondary_sector": secondary_sector.strip(),
        "sub_category": sub_category.strip(),
        "functional_expertise": functional_expertise.strip(),
        "linkedin": linkedin.strip(),
        "interests": interests.strip(),
        "investment_thesis": investment_thesis.strip(),
        "offering": offering.strip(),
        "needs": needs.strip(),
        "desired_connections": desired_connections.strip(),
    }

    if existing:
        db.update_profile(existing["id"], data)
        st.session_state["profile_id"] = existing["id"]
    else:
        data["source"] = "new"
        data["original_excel_row"] = None
        data["consent"] = 0
        data["consent_date"] = None
        new_id = db.create_profile(data)
        st.session_state["profile_id"] = new_id
        st.session_state["is_new_profile"] = False

    st.session_state["duplicate_warning_shown"] = False
    go_to("consent")


# ---------------------------------------------------------------------------
# STAGE: consent
# ---------------------------------------------------------------------------

CONSENT_TEXT = (
    "I agree to participate in VC Institute Connection and authorize my name, email address, "
    "and LinkedIn profile to be shared with participants who receive my profile as a recommended connection."
)


def render_consent_stage():
    st.subheader("Consent to participate")
    st.write("Before we generate your recommended connections, please confirm the following:")

    agree = st.checkbox(CONSENT_TEXT)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Continue"):
            profile = db.get_profile_by_id(st.session_state["profile_id"])
            if not agree:
                st.error("You must accept this statement to view your recommended connections.")
                return
            db.update_profile(profile["id"], {"consent": 1, "consent_date": db.now_iso()})

            # Generar recomendaciones ahora que hay consentimiento
            profile = db.get_profile_by_id(profile["id"])
            recommendations = matching.generate_recommendations(profile)
            db.save_recommendations(profile["id"], recommendations)

            go_to("connections")

    with col2:
        if st.button("Not now"):
            profile = db.get_profile_by_id(st.session_state["profile_id"])
            db.update_profile(profile["id"], {"consent": 0})
            st.info(
                "No problem. Your profile has been saved, but we won't generate or share any "
                "connections until you come back and accept."
            )


# ---------------------------------------------------------------------------
# STAGE: connections
# ---------------------------------------------------------------------------

def build_mailto_link(name, email):
    subject = "Connection through VC Institute Connection"
    body = (
        f"Hi {name}, VC Institute Connection recommended that we connect based on our shared "
        f"and complementary interests. I would be glad to meet you and explore potential areas "
        f"for collaboration."
    )
    return f"mailto:{email}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"


def render_connections_stage():
    st.subheader("Your recommended connections")

    profile = db.get_profile_by_id(st.session_state["profile_id"])
    if not profile or not profile["consent"]:
        st.warning("You need to accept the consent statement first.")
        if st.button("Go to consent step"):
            go_to("consent")
        return

    recommendations = db.get_recommendations_for_profile(profile["id"])

    if not recommendations:
        st.info(
            "We don't have any recommended connections for you yet. This can happen if not enough "
            "other participants have completed their profiles and accepted to participate. "
            "Please check back later."
        )
    else:
        for rec in recommendations:
            first_name = rec["full_name"].split(" ")[0]
            with st.container():
                st.markdown('<div class="match-card">', unsafe_allow_html=True)
                st.markdown(f"### {rec['full_name']}")
                st.markdown(f"<span class='match-score'>Match: {int(rec['score'])}%</span>", unsafe_allow_html=True)

                context_line = " · ".join(
                    [v for v in [rec.get("organization"), rec.get("current_role") or rec.get("current_context"), rec.get("geography")] if v]
                )
                if context_line:
                    st.caption(context_line)

                st.write("**Why you should talk**")
                st.write(rec["reason"])

                if rec["conversation_topics"]:
                    st.write("**Topics to start the conversation**")
                    for t in rec["conversation_topics"]:
                        st.write(f"- {t}")

                if rec.get("offering"):
                    st.write(f"**What they can offer:** {rec['offering']}")
                if rec.get("needs"):
                    st.write(f"**What they are looking for:** {rec['needs']}")

                st.write("**Contact**")
                st.write(rec["email"])
                if rec.get("linkedin"):
                    st.write(rec["linkedin"])

                mailto = build_mailto_link(first_name, rec["email"])
                st.link_button("Contact via email", mailto)

                st.markdown("</div>", unsafe_allow_html=True)

    st.divider()
    if st.button("Continue to feedback"):
        go_to("feedback")


# ---------------------------------------------------------------------------
# STAGE: feedback
# ---------------------------------------------------------------------------

RESULT_OPTIONS = [
    "We shared knowledge",
    "We identified common interests",
    "A possible collaboration came up",
    "A possible investment came up",
    "An introduction or contact came up",
    "We agreed to talk again",
    "There wasn't enough of a fit",
    "Other",
]


def render_feedback_stage():
    st.subheader("Was this connection useful?")

    profile = db.get_profile_by_id(st.session_state["profile_id"])
    recommendations = db.get_recommendations_for_profile(profile["id"])

    if not recommendations:
        st.info("You don't have any recommended connections to evaluate yet.")
        return

    already_evaluated_ids = {
        f["evaluated_profile_id"] for f in db.get_feedback_given(profile["id"])
    }

    pending = [r for r in recommendations if r["recommended_profile_id"] not in already_evaluated_ids]

    if not pending:
        st.success("You have already shared feedback for all of your recommended connections. Thank you!")
        return

    options = {r["full_name"]: r for r in pending}
    selected_name = st.selectbox("Which connection would you like to evaluate?", list(options.keys()))
    selected = options[selected_name]

    with st.form("feedback_form"):
        contacted = st.radio("Did you have a conversation with this person?", ["Yes", "Not yet"])

        usefulness_score = None
        result_type = None
        if contacted == "Yes":
            usefulness_score = st.select_slider(
                "How useful was the conversation?",
                options=[1, 2, 3, 4, 5],
                value=3,
                format_func=lambda v: {1: "1: Not useful", 5: "5: Very useful"}.get(v, str(v)),
            )
            result_type = st.selectbox("What happened as a result of the conversation?", RESULT_OPTIONS)

        comment = st.text_area("Comment (optional)")

        submitted = st.form_submit_button("Submit feedback")

    if submitted:
        db.save_feedback({
            "evaluator_profile_id": profile["id"],
            "evaluated_profile_id": selected["recommended_profile_id"],
            "contacted": "yes" if contacted == "Yes" else "not_yet",
            "usefulness_score": usefulness_score,
            "result_type": result_type,
            "comment": comment.strip() or None,
        })
        st.success("Thank you! Your feedback has been saved.")
        st.rerun()


# ---------------------------------------------------------------------------
# Panel de administrador (barra lateral, protegido con contraseña)
# ---------------------------------------------------------------------------

def render_admin_panel():
    with st.sidebar:
        st.markdown("### Administrator")
        password = st.text_input("Admin password", type="password", key="admin_password")

        if not password:
            return

        # Acceso seguro a st.secrets: si no existe el archivo secrets.toml, no debe romper la app.
        try:
            expected = st.secrets["ADMIN_PASSWORD"]
        except Exception:
            expected = None

        if not expected:
            st.warning("ADMIN_PASSWORD is not configured in st.secrets.")
            return

        if password != expected:
            st.error("Incorrect password.")
            return

        st.success("Access granted.")
        profiles_df = db.get_all_profiles_df()
        feedback_df = db.get_all_feedback_df()

        updated_profiles = profiles_df[profiles_df["source"] == "excel"]
        new_profiles = profiles_df[profiles_df["source"] == "new"]

        st.download_button(
            "Download updated profiles (CSV)",
            updated_profiles.to_csv(index=False).encode("utf-8"),
            file_name="updated_profiles.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download new profiles (CSV)",
            new_profiles.to_csv(index=False).encode("utf-8"),
            file_name="new_profiles.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download feedback (CSV)",
            feedback_df.to_csv(index=False).encode("utf-8"),
            file_name="feedback.csv",
            mime="text/csv",
        )


# ---------------------------------------------------------------------------
# Router principal
# ---------------------------------------------------------------------------

def main():
    render_admin_panel()
    render_progress()

    stage = st.session_state["stage"]
    if stage == "search":
        render_search_stage()
    elif stage == "profile_form":
        render_profile_form_stage()
    elif stage == "consent":
        render_consent_stage()
    elif stage == "connections":
        render_connections_stage()
    elif stage == "feedback":
        render_feedback_stage()
    else:
        st.session_state["stage"] = "search"
        st.rerun()


if __name__ == "__main__":
    main()
