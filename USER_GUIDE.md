# PIV Manager User Guide

## 1. Start and sign in

From the project folder in PowerShell, activate the virtual environment and start the app:

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

Open the local URL printed in the terminal, normally `http://localhost:8501`.

On a new database, create the first administrator. There is no default account. On later visits, sign in with an active account. Select **Sign out** in the sidebar when finished. The database and uploaded documents are stored locally; the default location is `%USERPROFILE%\.piv_manager`.

## 2. Roles and permissions

| Role | Typical access |
| --- | --- |
| Admin | Create and edit records, manage accounts, approve final validation, back up and restore the database |
| Editor | Create and edit operational records; cannot approve final validation or manage accounts |
| Approver | Review and record final validation decisions; other record-edit forms are read-only |
| Viewer | Read-only access |

Final decisions are authorized against the active account stored in the database. Account creation and significant record updates are recorded in the audit trail. At least one active administrator must remain.

## 3. Recommended workflow

1. Create the project and its component/part-revision records.
2. Add suppliers and contacts, then associate suppliers with components.
3. Plan required tests, sample deliveries, and APQP/PIV milestones.
4. Record supplier deliveries and conformity checks as they occur.
5. Update test results and attach reports. Create an NC for failures, or enter a documented disposition.
6. Track corrective actions, root cause, effectiveness evidence, and closure.
7. Review schedule changes, readiness criteria, and the approval history.
8. Export reports and create verified database backups as part of project closeout.

The Dashboard is a live view of database records, not a sample-data screen. Filters include project, supplier, component, and activity date range. Upcoming deadlines cover the next 30 days when no date range is selected.

## 4. Projects & PIV

Use **Projects & PIV** to create a project with its name, vehicle program, owners, dates, and phase. The application assigns a project code. Add one or more components with a part number, revision, and optional supplier.

Use **Edit / archive** to change project details, phase, status, target date, and actual completion date. Archiving hides a project from active-project selectors while retaining its associated history. Confirm the archive action before applying it.

The project list supports text search and status filtering. Component records are listed with their supplier and part revision. Create suppliers before assigning them to components.

## 5. Suppliers, samples, and visits

In **Suppliers & samples**:

- Create or edit supplier name, site, email, and phone.
- Add named contacts and mark a primary contact.
- Record a sample/prototype requirement against a project, component, and supplier, including required quantity and required/committed dates.
- Use **Record receipt / inspection** to record actual receipt date, quantity, conformity, and notes.
- Record supplier visits, purpose, visitors, project, and findings.
- Review delivery timing, conformity, and action-closure rates in **Performance**. Rates are based only on recorded delivery and action data; blank rates mean there is not enough recorded data.

Use the **Quality actions** page to create and close actions arising from a supplier visit.

## 6. Validation tests

In **Validation tests**, choose **Plan test** to record a test against a project and optional component/supplier. Available categories are Component test, Bench test, Laboratory test, Environmental test, Durability test, and Vehicle test. Record the requirement, owner, test location, laboratory, planned dates, sample quantity/availability, required documents, acceptance criteria, and whether the test is mandatory for final validation.

Test statuses are **Not Planned**, **Planned**, **Ready**, **In Progress**, **Passed**, **Failed**, **Blocked**, and **Retest Required**. Use **Record result** to save status, result, actual test date, report reference, sample availability, disposition, and comments. Each status update is retained in **Test history**.

A failed test must have a linked non-conformity or a written justified disposition. To plan a retest, select the original test in **Original test (for retest)**. The original result remains in its history, and the new test retains a link to it.

## 7. Non-conformities and actions

In **Quality actions**, create an NC with its project, originating test (if applicable), component, supplier, detection date, severity, description, and containment measures. Add investigation details using **5 Why analysis** and/or **Ishikawa / fishbone analysis**. Track an immediate correction and effectiveness verification.

Statuses are **Open**, **Containment**, **Root Cause Analysis**, **Action in Progress**, **Verification**, and **Closed**. An NC cannot be closed while linked actions remain open. Closure also requires a completed effectiveness verification and a named closure approver.

Create actions from the **Action plan** tab and link them to an NC when appropriate. Every action needs a description, responsible person, due date, and priority. Filters are available for owner, priority, project, supplier, and status. Closing an action requires evidence. A mandatory action also requires written effectiveness verification and the **Effectiveness verified** confirmation.

Overdue status is calculated using the current date. Closed and cancelled actions are not treated as overdue.

## 8. Planning and milestones

Use **Planning & milestones** to select a project, review its Gantt-style schedule, and compare baseline, current planned, and actual dates. Add APQP/PIV milestones with a planned date, owner, and mandatory flag. Update milestone status and actual completion date as work progresses.

Use **Reschedule test** when a planned test date changes. Enter a reason. Original planned dates are retained as the baseline, and each schedule change is listed in the history. Mandatory overdue or blocked items are highlighted as critical-path risks; this is a status-based warning, not a calculated dependency network.

## 9. Final validation / OK final

Open **Final validation**, select a project, and choose **Entire project** or a component scope. Readiness is calculated from recorded data. The checklist shows each criterion as met or pending.

The checks include:

- At least one mandatory test exists and every mandatory test is passed.
- Mandatory test reports have references; required test documents are attached to their test records.
- Mandatory test sample availability is recorded. If a supplier sample record exists in scope, its quantity must be received and marked conforming.
- Critical NCs are closed.
- Mandatory actions are closed and their effectiveness is verified.
- The four manual evidence items below are marked satisfied with a reference:
  - Mandatory test reports received and approved.
  - Required samples and documents available.
  - Supplier conformity confirmed.
  - Required reviews and approvals recorded.

An empty mandatory-test set is not considered ready. Manual checklist confirmations cannot override failed data checks. Admins and approvers can record **Ready for Review**, **Approved**, **Rejected**, **On Hold**, or **Not Ready**. **Approved** is rejected while any readiness item is pending. Decisions, comments, approver, and a readiness snapshot are retained in the decision history.

## 10. Documents

Use **Documents** to attach a file to a project, component, test, supplier, NC, or action, or store it without a record link. Supported extensions are PDF, DOC/DOCX, XLS/XLSX, CSV, TXT, PNG, JPG/JPEG, and TIF/TIFF. Files must be non-empty and no larger than 25 MB.

Files are stored under the configured local documents directory with unique generated filenames, so uploading the same source filename does not silently replace an existing file. Metadata and record links are stored in SQLite. The Documents page supports downloading stored files. Attach test reports to the test record so final readiness can find required test documents.

## 11. Reports and exports

In **Reports & exports**, choose a report and optionally filter by project. Where those fields exist, filter by status, severity, priority, supplier, or date range before downloading.

Available reports:

- Project validation summary.
- Detailed PIV tracking.
- Test status and results.
- Supplier delivery and conformity.
- Open non-conformities.
- Overdue actions.
- Final validation readiness.

Download either CSV or Excel (`.xlsx`). The report includes the records matching the selected filters; empty results represent no matching stored records.

## 12. Accounts, backups, and recovery

Only administrators can open **Administration**. Create additional accounts with a role and a password of at least 12 characters. Passwords are stored as salted PBKDF2 hashes. Deactivated users lose access on their next interaction; the last active administrator and your own account cannot be deactivated.

Select **Create verified backup** to make an integrity-checked SQLite backup. Backups are stored under `%USERPROFILE%\.piv_manager\backups` by default. Keep them protected because they contain operational and user data.

To restore, select a SQLite backup and confirm the warning. PIV Manager creates a safety backup of the current database before replacing it. A restore replaces current records with the chosen backup. Keep the app on the same workstation while restoring and verify project/test records after the restore.

## 13. Local deployment notes

The local SQLite deployment is designed for one workstation or controlled small-scale use, not unrestricted concurrent access over a shared network drive. Keep the database and documents directory on reliable local storage, restrict Windows account access, and back up both the SQLite database and the document files. The database backup does not include uploaded document files, so include the documents directory in your organization’s backup routine.

To change paths, set `PIV_MANAGER_DATA_DIR`, `PIV_MANAGER_DATABASE`, or `PIV_MANAGER_DOCUMENTS_DIR` before launching Streamlit. See [README.md](README.md) for installation and launch instructions.