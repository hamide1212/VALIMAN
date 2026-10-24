import streamlit as st

from piv_manager.auth import authenticate, create_user, get_active_user, user_count
from piv_manager.config import APP_NAME, DATABASE_PATH, DOCUMENTS_DIR
from piv_manager.db import initialize_database
from piv_manager.pages import (
    admin,
    dashboard,
    documents,
    planning,
    projects,
    quality,
    reports,
    suppliers,
    tests,
    validation,
)
from piv_manager.ui_common import report_error


st.set_page_config(page_title=APP_NAME, layout="wide")
initialize_database(DATABASE_PATH)
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)

st.markdown("""
<style>
    :root { --piv-ink: #24343d; --piv-green: #25815e; --piv-red: #b7463c; --piv-amber: #bd7a19; }
    .stApp { background: #f4f6f4; color: var(--piv-ink); }
    [data-testid="stSidebar"] { background: #e7ece8; border-right: 1px solid #ccd5cf; color: var(--piv-ink); }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label { color: var(--piv-ink) !important; }
    [data-testid="stMetric"] { background: #ffffff; border: 1px solid #dce3de; padding: 14px; border-radius: 6px; }
    div[data-testid="stForm"] { border-color: #dce3de; }
    [data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label { color: var(--piv-ink) !important; font-weight: 600; }
    h1, h2, h3 { color: #24343d; line-height: 1.25; }
    h1 { font-size: 2.2rem; }
    h2 { padding-bottom: 0.35rem; border-bottom: 1px solid #d3dcd6; }
    h3 { font-size: 1.35rem; }
</style>
""", unsafe_allow_html=True)


def show_first_admin_setup():
    st.title("PIV Manager")
    st.subheader("Initial administrator setup")
    st.info("Create the first local administrator. Passwords are stored as salted PBKDF2 hashes.")
    with st.form("first_admin"):
        username = st.text_input("Username")
        display_name = st.text_input("Display name")
        password = st.text_input("Password (at least 12 characters)", type="password")
        confirmation = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create administrator", type="primary")
    if submitted:
        if password != confirmation:
            st.error("Passwords do not match.")
        else:
            try:
                create_user(DATABASE_PATH, username=username, display_name=display_name,
                            password=password, role="admin", first_account=True)
                st.success("Administrator created. Sign in to continue.")
                st.rerun()
            except Exception as error:
                report_error(error)


def show_login():
    st.title("PIV Manager")
    st.subheader("Sign in")
    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary")
    if submitted:
        user = authenticate(DATABASE_PATH, username, password)
        if user:
            st.session_state["user"] = user
            st.rerun()
        st.error("Username or password is incorrect.")


if user_count(DATABASE_PATH) == 0:
    show_first_admin_setup()
    st.stop()

if "user" not in st.session_state:
    show_login()
    st.stop()

user = st.session_state["user"]
current_user = get_active_user(DATABASE_PATH, user["id"])
if current_user is None:
    del st.session_state["user"]
    st.warning("This account is no longer active. Sign in with an active account.")
    st.stop()
st.session_state["user"] = user = current_user
can_edit = user["role"] in {"admin", "editor"}
st.sidebar.markdown(f"## {APP_NAME}")
st.sidebar.caption(f"{user['display_name']} · {user['role'].title()}")
page = st.sidebar.radio("Navigation", [
    "Dashboard", "Projects & PIV", "Validation tests", "Suppliers & samples",
    "Quality actions", "Planning & milestones", "Final validation", "Reports & exports",
    "Documents", "Administration",
], label_visibility="collapsed")
if st.sidebar.button("Sign out"):
    del st.session_state["user"]
    st.rerun()

if page == "Dashboard":
    dashboard.render(DATABASE_PATH)
elif page == "Projects & PIV":
    projects.render(DATABASE_PATH, user, can_edit)
elif page == "Validation tests":
    tests.render(DATABASE_PATH, user, can_edit)
elif page == "Suppliers & samples":
    suppliers.render(DATABASE_PATH, user, can_edit)
elif page == "Quality actions":
    quality.render(DATABASE_PATH, user, can_edit)
elif page == "Planning & milestones":
    planning.render(DATABASE_PATH, user, can_edit)
elif page == "Final validation":
    validation.render(DATABASE_PATH, user, can_edit)
elif page == "Reports & exports":
    reports.render(DATABASE_PATH)
elif page == "Documents":
    documents.render(DATABASE_PATH, user, can_edit)
else:
    if user["role"] == "admin":
        admin.render(DATABASE_PATH, user)
    else:
        st.title("Administration")
        st.info("Administrator role required.")