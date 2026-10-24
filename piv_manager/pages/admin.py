from datetime import datetime
from pathlib import Path
import tempfile

import streamlit as st

from piv_manager.auth import create_user, list_users, set_user_active
from piv_manager.config import DATA_DIR, DATABASE_PATH
from piv_manager.services import backup_database, restore_database
from piv_manager.ui_common import report_error, rows, show_rows


def render(database_path, user):
    st.title("Administration")
    st.caption("Accounts · Database recovery · Audit trail")
    user_rows = list_users(database_path)
    with st.expander("Manage accounts", expanded=False):
        with st.form("create_user", clear_on_submit=True):
            username = st.text_input("Username")
            display_name = st.text_input("Display name")
            password = st.text_input("Temporary password (12+ characters)", type="password")
            role = st.selectbox("Role", ["admin", "approver", "editor", "viewer"])
            submit = st.form_submit_button("Create account")
        if submit:
            try:
                create_user(database_path, username=username, display_name=display_name,
                            password=password, role=role)
                st.success("Account created.")
                st.rerun()
            except Exception as error:
                report_error(error)
        show_rows(user_rows)
        active_users = [u for u in user_rows if u["active"]]
        if active_users:
            account_labels = [f"{u['username']} · {u['role']}" for u in active_users]
            selected = st.selectbox("Deactivate account", account_labels)
            target = active_users[account_labels.index(selected)]
            confirm = st.checkbox("Confirm account deactivation")
            if st.button("Deactivate", disabled=not confirm or target["id"] == user["id"]):
                try:
                    set_user_active(database_path, target["id"], False, user["username"])
                    st.success("Account deactivated.")
                    st.rerun()
                except Exception as error:
                    report_error(error)

    st.markdown("#### Database backup")
    backup_dir = DATA_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    if st.button("Create verified backup"):
        name = f"piv-manager-{datetime.now():%Y%m%d-%H%M%S}.sqlite3"
        try:
            path = backup_database(database_path, backup_dir / name)
            st.success(f"Backup created and integrity-checked: {path}")
        except Exception as error:
            report_error(error)
    backup_files = sorted(backup_dir.glob("*.sqlite3"), key=lambda path: path.stat().st_mtime, reverse=True)
    if backup_files:
        st.dataframe([{"Backup": path.name, "Size (bytes)": path.stat().st_size}
                      for path in backup_files], width="stretch", hide_index=True)
    st.markdown("#### Restore database")
    st.warning("Restore replaces current database contents. A verified safety backup is created first.")
    restore_file = st.file_uploader("Backup file", type=["sqlite3", "db"])
    confirm_restore = st.checkbox("I understand that restoring replaces current records")
    if st.button("Restore selected backup", disabled=restore_file is None or not confirm_restore):
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as temporary:
                temporary.write(restore_file.getvalue())
                temporary_path = Path(temporary.name)
            safety_path = backup_dir / f"before-restore-{datetime.now():%Y%m%d-%H%M%S}.sqlite3"
            backup_database(database_path, safety_path)
            restore_database(database_path, temporary_path)
            st.success(f"Database restored. Safety copy: {safety_path.name}")
            st.rerun()
        except Exception as error:
            report_error(error)
        finally:
            if temporary_path:
                temporary_path.unlink(missing_ok=True)

    st.markdown("#### Audit events")
    show_rows(rows(database_path, """SELECT occurred_at, username, entity_type,
        entity_id, operation, details FROM audit_events ORDER BY id DESC LIMIT 250"""),
        "No audit events recorded.")