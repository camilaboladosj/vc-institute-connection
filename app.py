"""VC INSTITUTE CONNECTION - Streamlit prototype.

A simple internal tool that lets VC Institute cohort members find their
profile (or create one), state their interests and what they can offer or
are looking for, consent to share their data, and receive rule-based,
TF-IDF driven connection recommendations with contact details.
"""

import urllib.parse
from datetime import datetime

import pandas as pd
import streamlit as st

import data_loader
import database
import matching
from explanations import build_explanation

st.set_page_config(page_title="VC INSTITUTE CONNECTION", page_icon=None, layout="centered")

STEPS = ["Profile", "Interests", "Consent", "Connections", "Evaluation"]
STAGE_TO_STEP = {
    "landing": 1,
    "review_profile": 1,
    "create_profile": 1,
    "matching_form": 2,
    "consent": 3,
    "recommendations": 4,
    "feedback": 5,
}

RESULT_TYPE_OPTIONS = [
    "We shared knowledge",
    "We identified common interests",
    "A potential collaboration emerged",
    "A potential investment emerged",
    "An introduction or contact emerged",
    "We agreed to talk again",
    "There wasn't enough alignment",
    "Other",
]

CONSENT_TEXT = (
    "I agree to participate in VC Institute Connection and authorize my name, "
    "email address, and LinkedIn profile to be shared with participants who "
    "receive my profile as a recommended connection."
)

EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


@st.cache_resource
def bootstrap():
    """Create the database and import Excel records once per app instance."""
    database.init_db()
    imported = data_loader.import_new_records()
    return imported


def init_session_state():
    defaults = {
        "stage": "landing",
        "search_query": "",
        "profile_id": None,
        "is_new_profile": False,
        "recommendations": None,
        "confirm_new_person": False,
        "feedback_target_id": None,
        "feedback_saved": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def go_to(stage):
    st.session_state.stage = stage


def render_header():
    st.markdown(
        "<h1 style='color:#0B2545; margin-bottom:0;'>VC INSTITUTE CONNECTION</h1>",
        unsafe_allow_html=True,
    )
    st.caption("Find people in the cohort worth connecting with.")


def render_progress():
    step = STAGE_TO_STEP.get(st.session_state.stage, 1)
    st.progress(step / len(STEPS))
    st.caption(f"Step {step} of {len(STEPS)}: {STEPS[step - 1]}")


def valid_email(email):
    import re

    return bool(re.match(EMAIL_REGEX, (email or "").strip()))


# --------------------------------------------------------------------------
# Stage: landing (search or create)
# --------------------------------------------------------------------------

def render_landing():
    st.subheader("Find your profile")
    query = st.text_input("Search your profile by name", value=st.session_state.search_query)
    st.session_state.search_query = query
    st.button("Find my profile", use_container_width=True)

    if query.strip():
        matches = database.search_profiles_by_name(query)
        if matches:
            st.write("Select your name from the list below:")
            for match in matches:
                label_parts = [match["full_name"]]
                extra = match.get("organization") or match.get("current_context") or match.get("geography")
                if extra:
                    label_parts.append(f"({extra[:40]})")
                label = " ".join(label_parts)
                if st.button(label, key=f"select_{match['id']}", use_container_width=True):
                    st.session_state.profile_id = match["id"]
                    st.session_state.is_new_profile = False
                    go_to("review_profile")
                    st.rerun()
        else:
            st.info("No matches found. You can create a new profile below.")

    st.divider()
    st.write("Not in the database?")
    if st.button("Create a profile", use_container_width=True):
        st.session_state.profile_id = None
        st.session_state.is_new_profile = True
        go_to("create_profile")
        st.rerun()


# --------------------------------------------------------------------------
# Stage: review_profile (existing Excel-sourced profile)
# --------------------------------------------------------------------------

def render_review_profile():
    profile = database.get_profile(st.session_state.profile_id)
    if not profile:
        st.error("We could not find that profile. Please search again.")
        if st.button("Back to search"):
            go_to("landing")
            st.rerun()
        return

    st.subheader("Review your information")
    st.success(
        "We found your profile. Review the information, add your email, "
        "and complete your interests."
    )

    with st.form("review_profile_form"):
        full_name = st.text_input("Name", value=profile.get("full_name") or "")
        email = st.text_input(
            "Email address (required)", value=profile.get("email") or ""
        )
        geography = st.text_input("Geography", value=profile.get("geography") or "")
        category = st.text_input("Category", value=profile.get("category") or "")
        organization = st.text_input(
            "Organization or company (optional)", value=profile.get("organization") or ""
        )
        discipline = st.text_input("Discipline", value=profile.get("discipline") or "")
        primary_sector = st.text_input(
            "Sector (Primary)", value=profile.get("primary_sector") or ""
        )
        secondary_sector = st.text_input(
            "Sector (Secondary)", value=profile.get("secondary_sector") or ""
        )
        functional_expertise = st.text_input(
            "Functional Expertise", value=profile.get("functional_expertise") or ""
        )
        current_context = st.text_area(
            "Current Role / Context", value=profile.get("current_context") or "", height=90
        )
        linkedin = st.text_input("LinkedIn (optional)", value=profile.get("linkedin") or "")

        submitted = st.form_submit_button("Save and continue", use_container_width=True)

    if submitted:
        errors = []
        if not full_name.strip():
            errors.append("Name is required.")
        if not valid_email(email):
            errors.append("A valid email address is required.")

        if errors:
            for error in errors:
                st.error(error)
        else:
            try:
                database.update_profile(
                    profile["id"],
                    {
                        "full_name": full_name.strip(),
                        "email": email.strip().lower(),
                        "geography": geography.strip(),
                        "category": category.strip(),
                        "organization": organization.strip(),
                        "discipline": discipline.strip(),
                        "primary_sector": primary_sector.strip(),
                        "secondary_sector": secondary_sector.strip(),
                        "functional_expertise": functional_expertise.strip(),
                        "current_context": current_context.strip(),
                        "linkedin": linkedin.strip(),
                    },
                )
                st.session_state.profile_id = profile["id"]
                go_to("matching_form")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    if st.button("Back to search"):
        go_to("landing")
        st.rerun()


# --------------------------------------------------------------------------
# Stage: create_profile (brand new participant)
# --------------------------------------------------------------------------

def render_create_profile():
    st.subheader("Create a profile")

    similar = []
    with st.form("create_profile_form"):
        full_name = st.text_input("Full name (required)")
        email = st.text_input("Email address (required)")
        geography = st.text_input("Geography, country, or region (required)")
        organization = st.text_input("Organization or company (required)")
        current_context = st.text_area(
            "Current role or professional context (required)", height=90
        )
        discipline = st.text_input("Main discipline (required)")
        primary_sector = st.text_input("Primary sector (required)")
        secondary_sector = st.text_input("Secondary sector (required)")
        functional_expertise = st.text_input("Functional expertise (required)")
        linkedin = st.text_input("LinkedIn (optional)")

        if full_name.strip():
            similar = database.find_similar_by_name(full_name)

        confirm_new_person = False
        if similar:
            st.warning(
                "We found existing profiles with a similar name: "
                + ", ".join(s["full_name"] for s in similar)
                + ". Please make sure this is not already you."
            )
            confirm_new_person = st.checkbox(
                "I confirm this is a different person and I want to create a new profile."
            )

        submitted = st.form_submit_button("Create profile and continue", use_container_width=True)

    if submitted:
        errors = []
        required_fields = {
            "Full name": full_name,
            "Email address": email,
            "Geography": geography,
            "Organization": organization,
            "Current role or context": current_context,
            "Discipline": discipline,
            "Primary sector": primary_sector,
            "Secondary sector": secondary_sector,
            "Functional expertise": functional_expertise,
        }
        for label, value in required_fields.items():
            if not value.strip():
                errors.append(f"{label} is required.")
        if not valid_email(email):
            errors.append("A valid email address is required.")
        if similar and not confirm_new_person:
            errors.append(
                "Please confirm you are a different person, or go back and search again."
            )

        if errors:
            for error in errors:
                st.error(error)
        else:
            try:
                new_id = database.create_profile(
                    {
                        "source": "new",
                        "full_name": full_name.strip(),
                        "email": email.strip().lower(),
                        "geography": geography.strip(),
                        "organization": organization.strip(),
                        "current_context": current_context.strip(),
                        "discipline": discipline.strip(),
                        "primary_sector": primary_sector.strip(),
                        "secondary_sector": secondary_sector.strip(),
                        "functional_expertise": functional_expertise.strip(),
                        "linkedin": linkedin.strip(),
                    }
                )
                st.session_state.profile_id = new_id
                go_to("matching_form")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    if st.button("Back to search"):
        go_to("landing")
        st.rerun()


# --------------------------------------------------------------------------
# Stage: matching_form (interests, thesis, offer, needs, desired connections)
# --------------------------------------------------------------------------

def render_matching_form():
    profile = database.get_profile(st.session_state.profile_id)
    if not profile:
        go_to("landing")
        st.rerun()
        return

    st.subheader("Complete your connection profile")
    st.write("Tell us more so we can recommend the right people to connect with.")

    with st.form("matching_form"):
        interests = st.text_area(
            "What are your main areas of interest?",
            value=profile.get("interests") or "",
            height=90,
            placeholder="e.g. Fintech, impact investing, AI, and startup development.",
        )
        investment_thesis = st.text_area(
            "What are you currently working on, or what is your investment thesis?",
            value=profile.get("investment_thesis") or "",
            height=90,
        )
        offering = st.text_area(
            "What can you offer other members of the cohort?",
            value=profile.get("offering") or "",
            height=90,
            placeholder="e.g. Experience in project evaluation, public innovation, and ecosystem building.",
        )
        needs = st.text_area(
            "What are you looking for within the cohort?",
            value=profile.get("needs") or "",
            height=90,
            placeholder="e.g. Meeting impact investors and people experienced in creative-industry funds.",
        )
        desired_connections = st.text_area(
            "What type of people would you like to connect with?",
            value=profile.get("desired_connections") or "",
            height=90,
        )

        submitted = st.form_submit_button("Save and continue", use_container_width=True)

    if submitted:
        errors = []
        if not interests.strip():
            errors.append("Please share your main areas of interest.")
        if not offering.strip():
            errors.append("Please share what you can offer other members.")
        if not needs.strip():
            errors.append("Please share what you are looking for.")

        if errors:
            for error in errors:
                st.error(error)
        else:
            database.update_profile(
                profile["id"],
                {
                    "interests": interests.strip(),
                    "investment_thesis": investment_thesis.strip(),
                    "offering": offering.strip(),
                    "needs": needs.strip(),
                    "desired_connections": desired_connections.strip(),
                },
            )
            go_to("consent")
            st.rerun()


# --------------------------------------------------------------------------
# Stage: consent
# --------------------------------------------------------------------------

def render_consent():
    profile = database.get_profile(st.session_state.profile_id)
    if not profile:
        go_to("landing")
        st.rerun()
        return

    st.subheader("Consent to participate")
    st.write(CONSENT_TEXT)
    agree = st.checkbox("I agree", value=bool(profile.get("consent")))

    if st.button("Confirm and see my connections", use_container_width=True):
        if not agree:
            st.error("You must agree to participate before we can generate connections.")
        else:
            database.update_profile(
                profile["id"],
                {"consent": 1, "consent_date": database.now_iso()},
            )
            refreshed = database.get_profile(profile["id"])
            results = matching.generate_recommendations(refreshed)
            to_save = []
            for result in results:
                reason, topics = build_explanation(refreshed, result["profile"])
                result["reason"] = reason
                result["conversation_topics"] = topics
                to_save.append(result)
            database.save_recommendations(profile["id"], to_save)
            st.session_state.recommendations = None
            go_to("recommendations")
            st.rerun()


# --------------------------------------------------------------------------
# Stage: recommendations
# --------------------------------------------------------------------------

def render_recommendations():
    profile = database.get_profile(st.session_state.profile_id)
    if not profile or not profile.get("consent"):
        go_to("consent")
        st.rerun()
        return

    st.subheader("Your recommended connections")
    recs = database.get_recommendations_for_user(profile["id"])

    if not recs:
        st.info(
            "We could not find any eligible matches yet. Check back once more "
            "cohort members have completed their profiles."
        )
    else:
        for rec in recs:
            with st.container(border=True):
                st.markdown(f"### {rec['full_name']}")
                st.markdown(f"**Match: {rec['score']:.0f}%**")

                subtitle_parts = []
                if rec.get("organization"):
                    subtitle_parts.append(rec["organization"])
                if rec.get("current_role"):
                    subtitle_parts.append(rec["current_role"])
                if rec.get("geography"):
                    subtitle_parts.append(rec["geography"])
                if subtitle_parts:
                    st.caption(" • ".join(subtitle_parts))

                st.markdown("**Why you should connect**")
                st.write(rec["reason"])

                topics = [t for t in (rec.get("conversation_topics") or "").split(" | ") if t]
                if topics:
                    st.markdown("**Topics to start the conversation**")
                    for topic in topics:
                        st.write(f"- {topic}")

                if rec.get("offering"):
                    st.markdown(f"**What they can offer:** {rec['offering']}")
                if rec.get("needs"):
                    st.markdown(f"**What they are looking for:** {rec['needs']}")

                st.markdown("**Contact**")
                st.write(rec["email"])
                if rec.get("linkedin"):
                    st.write(rec["linkedin"])

                subject = urllib.parse.quote("Connection through VC Institute Connection")
                body = urllib.parse.quote(
                    f"Hi {rec['full_name']}, VC Institute Connection recommended that we "
                    "connect based on our shared and complementary interests. I would be "
                    "glad to meet you and explore potential areas for collaboration."
                )
                mailto = f"mailto:{rec['email']}?subject={subject}&body={body}"
                st.link_button("Contact via email", mailto, use_container_width=True)

    if st.button("Continue to feedback", use_container_width=True):
        go_to("feedback")
        st.rerun()


# --------------------------------------------------------------------------
# Stage: feedback
# --------------------------------------------------------------------------

def render_feedback():
    profile = database.get_profile(st.session_state.profile_id)
    if not profile:
        go_to("landing")
        st.rerun()
        return

    st.subheader("Was this connection useful?")
    recs = database.get_recommendations_for_user(profile["id"])

    if not recs:
        st.info("You do not have any recommended connections to evaluate yet.")
        return

    options = {rec["recommended_profile_id"]: rec["full_name"] for rec in recs}
    selected_id = st.selectbox(
        "Select which connection you want to evaluate",
        options=list(options.keys()),
        format_func=lambda pid: options[pid],
    )

    with st.form("feedback_form"):
        contacted = st.radio(
            "Did you have a conversation with this person?", ["Yes", "Not yet"]
        )

        usefulness_score = None
        result_type = None
        if contacted == "Yes":
            usefulness_score = st.slider(
                "How useful was the conversation? (1 = not useful, 5 = very useful)", 1, 5, 3
            )
            result_type = st.selectbox(
                "What happened as a result of the conversation?", RESULT_TYPE_OPTIONS
            )

        comment = st.text_area("Comment (optional)", height=80)
        submitted = st.form_submit_button("Save feedback", use_container_width=True)

    if submitted:
        database.save_feedback(
            {
                "evaluator_profile_id": profile["id"],
                "evaluated_profile_id": selected_id,
                "contacted": "yes" if contacted == "Yes" else "not_yet",
                "usefulness_score": usefulness_score,
                "result_type": result_type,
                "comment": comment.strip() or None,
            }
        )
        st.success("Thank you. Your feedback has been saved.")

    st.divider()
    if st.button("Back to my connections", use_container_width=True):
        go_to("recommendations")
        st.rerun()


# --------------------------------------------------------------------------
# Admin section (sidebar)
# --------------------------------------------------------------------------

def render_admin_sidebar():
    with st.sidebar:
        st.markdown("### Administrator")
        password = st.text_input("Admin password", type="password", key="admin_password")
        expected = st.secrets.get("ADMIN_PASSWORD") if hasattr(st, "secrets") else None

        if not expected:
            st.caption("Set ADMIN_PASSWORD in Streamlit secrets to enable exports.")
            return

        if password and password == expected:
            st.success("Access granted.")
            profiles_df = database.get_all_profiles_df()

            updated_profiles = profiles_df[
                (profiles_df["source"] == "excel")
                & (profiles_df["updated_at"] != profiles_df["created_at"])
            ]
            new_profiles = profiles_df[profiles_df["source"] == "new"]
            feedback_df = database.get_all_feedback_df()

            st.download_button(
                "Download updated profiles (CSV)",
                updated_profiles.to_csv(index=False).encode("utf-8"),
                file_name="updated_profiles.csv",
                mime="text/csv",
                use_container_width=True,
            )
            st.download_button(
                "Download new profiles (CSV)",
                new_profiles.to_csv(index=False).encode("utf-8"),
                file_name="new_profiles.csv",
                mime="text/csv",
                use_container_width=True,
            )
            st.download_button(
                "Download feedback (CSV)",
                feedback_df.to_csv(index=False).encode("utf-8"),
                file_name="feedback.csv",
                mime="text/csv",
                use_container_width=True,
            )
        elif password:
            st.error("Incorrect password.")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    bootstrap()
    init_session_state()
    render_header()
    render_progress()
    render_admin_sidebar()

    stage = st.session_state.stage
    if stage == "landing":
        render_landing()
    elif stage == "review_profile":
        render_review_profile()
    elif stage == "create_profile":
        render_create_profile()
    elif stage == "matching_form":
        render_matching_form()
    elif stage == "consent":
        render_consent()
    elif stage == "recommendations":
        render_recommendations()
    elif stage == "feedback":
        render_feedback()
    else:
        go_to("landing")
        st.rerun()


if __name__ == "__main__":
    main()
