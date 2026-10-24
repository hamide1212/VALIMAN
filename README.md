# PIV Manager

Local automotive validation management built with Streamlit, SQLite, Pandas, and Plotly.

## Windows setup

1. Install Python 3.11 or later and open this folder in Visual Studio Code.
2. In the VS Code terminal, create and activate a virtual environment:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies and launch:

   ```powershell
   python -m pip install -r requirements.txt
   streamlit run app.py
   ```

The default database and document directory are under `%USERPROFILE%\.piv_manager`. Set `PIV_MANAGER_DATA_DIR`, `PIV_MANAGER_DATABASE`, or `PIV_MANAGER_DOCUMENTS_DIR` to change them. The application creates its schema on first launch and retains data across upgrades through versioned migrations.

On the first launch, create the initial administrator account in the browser. There is no default username or password. Administrators can create editor, approver, viewer, and additional administrator accounts from **Administration**. Passwords are stored as salted PBKDF2 hashes.

See [USER_GUIDE.md](USER_GUIDE.md) for module workflows, readiness rules, reports, document handling, and backup/restore instructions.

## Verification

Run the business-rule and integration tests with:

```powershell
python -m unittest discover -s tests -v
```

The application includes project/component, supplier/contact, test/retest, sample delivery, action, non-conformity, APQP planning, readiness/approval, reporting/export, document, audit, and database backup/restore workflows. Final approval is blocked until mandatory tests, reports, sample/supplier checks, critical NCs, actions, and review evidence meet the readiness rules.

## Streamlit Community Cloud

1. Push this project to a GitHub repository.
2. In Streamlit Community Cloud, create an app from that repository and select `app.py` as the main file.
3. Deploy. The repository already includes `.streamlit/config.toml` and `requirements.txt`.
4. Create the initial administrator in the browser on first launch. Do not add local database files, uploaded documents, or passwords to GitHub.

The app can run on Community Cloud, but its SQLite database and uploaded files live on the app machine's local filesystem. That filesystem is not a durable production database or file store across app restarts/redeployments. Use Community Cloud for a demo only unless you replace local SQLite/files with durable managed storage and configure an appropriate backup strategy. See [USER_GUIDE.md](USER_GUIDE.md) for local data and backup details.

Verified database backups are stored in `%USERPROFILE%\.piv_manager\backups`. Documents use unique stored filenames under `%USERPROFILE%\.piv_manager\documents`; existing files are never silently replaced.

## Deployment note

This SQLite deployment is intended for a single workstation or controlled small-scale use. It is not designed for unrestricted concurrent access over a network share. User roles and approval controls are enforced inside the application; protect the workstation and backup directory accordingly. Backups contain operational and user data, so store them with the same access protections as the live database.
