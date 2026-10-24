import pandas as pd
import streamlit as st

from piv_manager.services import approve_validation, get_readiness, set_checklist_item
from piv_manager.ui_common import choice_options, report_error, require_editor, rows


MANUAL_CRITERIA = [
    ("Mandatory test reports received and approved", "Test reports"),
    ("Required samples and documents available", "Samples and documents"),
    ("Supplier conformity confirmed", "Supplier quality"),
    ("Required reviews and approvals recorded", "Reviews and approvals"),
]


def render(database_path, user, can_edit):
    st.title("Final validation · OK final")
    st.caption("Readiness evidence · Authorized decision · Approval history")
    projects = rows(database_path, "SELECT id, name FROM projects WHERE archived=0 ORDER BY name")
    project_labels, project_map = choice_options(projects)
    if not project_labels:
        st.info("Create a project to evaluate final validation readiness.")
        return
    project_label = st.selectbox("Project", project_labels)
    project_id = project_map[project_label]
    components = rows(database_path, "SELECT id, name FROM components WHERE project_id=? ORDER BY name",
                      (project_id,))
    component_labels, component_map = choice_options(components)
    component_label = st.selectbox("Validation scope", ["Entire project", *component_labels])
    component_id = component_map.get(component_label)
    readiness = get_readiness(database_path, project_id, component_id)
    status = "Ready for Review" if readiness["ready"] else "Not Ready"
    st.markdown(f"### Current status: **{status}**")
    checks = pd.DataFrame([{"Criterion": name, "Result": "Met" if ok else "Pending"}
                           for name, ok in readiness["criteria"].items()])
    st.dataframe(checks, width="stretch", hide_index=True)
    if readiness["pending"]:
        st.warning("Final OK is blocked until every mandatory criterion is met.")
    else:
        st.success("Mandatory validation criteria are evidenced. The authorized approver may review the decision.")

    if require_editor(can_edit):
        with st.expander("Record checklist evidence", expanded=bool(readiness["pending"])):
            existing = {item["criterion"]: item for item in rows(
                database_path,
                "SELECT * FROM checklist_items WHERE project_id=? AND component_id IS ?",
                (project_id, component_id),
            )}
            for criterion, category in MANUAL_CRITERIA:
                item = existing.get(criterion)
                with st.form(f"check_{criterion}"):
                    satisfied = st.checkbox(criterion, value=bool(item["satisfied"]) if item else False)
                    evidence = st.text_input("Evidence / reference", value=item["evidence"] if item else "")
                    submit = st.form_submit_button("Save evidence")
                if submit:
                    try:
                        set_checklist_item(database_path, project_id=project_id,
                                           criterion=criterion, category=category,
                                           satisfied=satisfied, evidence=evidence,
                                           component_id=component_id,
                                           checked_by=user["username"])
                        st.success("Checklist evidence updated.")
                        st.rerun()
                    except Exception as error:
                        report_error(error)
    st.markdown("#### Decision")
    if user["role"] not in {"admin", "approver"}:
        st.info("Only an administrator or authorized approver can record final validation decisions.")
    else:
        with st.form("final_decision"):
            decision = st.selectbox("Decision", ["Ready for Review", "Approved", "Rejected", "On Hold", "Not Ready"])
            comments = st.text_area("Decision comments")
            submit = st.form_submit_button("Record decision", type="primary")
        if submit:
            try:
                approve_validation(database_path, project_id=project_id,
                                   approver=user["display_name"],
                                   approver_user_id=user["id"],
                                   comments=comments, decision=decision,
                                   component_id=component_id)
                st.success("Validation decision recorded.")
                st.rerun()
            except Exception as error:
                report_error(error)
    st.markdown("#### Decision history")
    history = rows(database_path, """SELECT decision, approver, decision_date, comments,
        readiness_snapshot FROM final_approval_history WHERE project_id=?
        AND ((component_id IS NULL AND ? IS NULL) OR component_id=?)
        ORDER BY decision_date DESC, id DESC""", (project_id, component_id, component_id))
    if history:
        st.dataframe(pd.DataFrame([dict(item) for item in history]), width="stretch", hide_index=True)
    else:
        st.info("No validation decisions have been recorded.")