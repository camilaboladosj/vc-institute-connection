# VC INSTITUTE CONNECTION

An internal prototype to help VC Institute cohort members find each other,
share their interests, and receive simple, transparent connection
recommendations.

## What this tool does

1. Search your profile by name (imported from the cohort's Excel roster).
2. Add your email address (the original Excel file has no emails).
3. Review and correct your information, or create a new profile if you are
   not in the file.
4. Describe your interests, what you can offer, and what you are looking for.
5. Consent to share your data with recommended connections.
6. Receive up to five recommended connections with an explanation and
   contact details.
7. Evaluate afterwards whether a connection was useful.

## Files in this project

- `app.py` - the Streamlit application (all screens and flow).
- `database.py` - SQLite schema and all read/write access.
- `data_loader.py` - reads `data/VC_Lab_C7_Introductions_v4.xlsx` and imports
  the `All People` sheet into the database on first run.
- `matching.py` - the TF-IDF / cosine-similarity matching engine.
- `explanations.py` - rule-based explanations for each match (no AI).
- `requirements.txt` - Python dependencies.
- `data/VC_Lab_C7_Introductions_v4.xlsx` - the original roster (read-only,
  never modified by the app).
- `.streamlit/config.toml` - visual theme.
- `vc_connection.db` - the SQLite database created automatically the first
  time you run the app (not included in the repository).

## Running it locally

You need Python 3.11 installed. Then, from the project folder:

```bash
python -m venv .venv
```

Activate the virtual environment:

- Windows: `.venv\Scripts\activate`
- macOS or Linux: `source .venv/bin/activate`

Install the dependencies and run the app:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Streamlit will open the app in your browser, usually at
`http://localhost:8501`. The first time it runs, it creates
`vc_connection.db` and imports every person from the `All People` sheet.

## Deploying to Streamlit Community Cloud

1. Create a GitHub repository (public or private) and upload every file in
   this project, keeping the same folder structure.
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with
   your GitHub account.
3. Click **New app** and select your repository and branch.
4. Set the main file path to `app.py`.
5. Click **Deploy**.
6. Once it finishes building, open the app link on your phone to try it.

### Setting the administrator password

The admin export section (see below) reads its password from Streamlit
secrets, never from the code. In Streamlit Community Cloud:

1. Open your app's settings, then **Secrets**.
2. Add:
   ```toml
   ADMIN_PASSWORD = "choose-a-password"
   ```
3. Save. Locally, you can create a `.streamlit/secrets.toml` file with the
   same content (it is excluded from git by `.gitignore`).

## Important limitation: data persistence

This prototype uses **SQLite**, a simple file-based database that requires
no external service or account setup. It works well for local use and for
trying the app on Streamlit Community Cloud.

However, **Streamlit Community Cloud's filesystem is not guaranteed to be
persistent.** If the app restarts, sleeps after inactivity, or is
redeployed, the `vc_connection.db` file (and everything saved in it -
edited profiles, new profiles, consents, recommendations, feedback) may be
reset. For a short pilot or demo this is usually fine, since the app will
simply re-import the original Excel roster on the next start. If you need
guaranteed long-term persistence, the database would need to be moved to an
external, always-on database service - which is outside the scope of this
prototype.

## Administrator exports

In the sidebar, entering the correct admin password unlocks three CSV
downloads:

- Updated profiles (Excel-sourced profiles that were edited in the app).
- New profiles (profiles created directly in the app).
- Feedback (all connection evaluations).

## Known limitations

- The original Excel file has no "Organization" column; it is captured as a
  new optional field when reviewing an existing profile, and as a required
  field when creating a new one.
- "Live" search suggestions update as Streamlit reruns the page (on each
  keystroke that changes the text box), not via a custom JavaScript
  autocomplete component.
- The matching engine and explanations are intentionally simple and
  rule-based, as requested - there is no external AI involved.
- This is an internal prototype, not a production system: there is no user
  authentication beyond searching by name and providing an email.
