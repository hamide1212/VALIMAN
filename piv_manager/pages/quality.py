from datetime import date

import streamlit as st

from piv_manager.services import (
    create_action,
    create_non_conformity,
    update_action,
    update_non_conformity,
)
from piv_manager.ui_common import choice_options, date_value, report_error, require_editor, rows, show_rows


NC_STATUSES = ["Open", "Containment", "Root Cause Analysis", "Action in Progress", "Verification", "Closed"]
ACTION_STATUSES = ["Open", "In Progress", "Blocked", "Closed", "Cancelled"]


def render(database_path, user, can_edit):
    st.title("Quality actions")
    st.caption("Non-conformities · Corrective action plan · Closure evidence")
    ncs = rows(database_path, """SELECT nc.*, p.name AS project, t.test_code,
        s.name AS supplier FROM non_conformities nc JOIN projects p ON p.id=nc.project_id
        LEFT JOIN tests t ON t.id=nc.test_id LEFT JOIN suppliers s ON s.id=nc.supplier_id
        ORDER BY CASE nc.severity WHEN 'Critical' THEN 0 WHEN 'Major' THEN 1 ELSE 2 END,
        nc.detected_date DESC""")
    actions = rows(database_path, """SELECT a.*, p.name AS project, s.name AS supplier,
        nc.nc_code FROM actions a JOIN projects p ON p.id=a.project_id
        LEFT JOIN suppliers s ON s.id=a.supplier_id LEFT JOIN non_conformities nc ON nc.id=a.nc_id
        ORDER BY CASE a.status WHEN 'Closed' THEN 1 ELSE 0 END, a.due_date""")
    tab_nc, tab_actions = st.tabs([f"Non-conformities ({len(ncs)})", f"Action plan ({len(actions)})"])
    projects = rows(database_path, "SELECT id, name FROM projects WHERE archived=0 ORDER BY name")
    project_labels, project_map = choice_options(projects)
    suppliers = rows(database_path, "SELECT id, name FROM suppliers WHERE archived=0 ORDER BY name")
    supplier_labels, supplier_map = choice_options(suppliers)
    with tab_nc:
        show_rows(ncs, "No non-conformities recorded.")
        if project_labels and require_editor(can_edit):
            with st.expander("Record non-conformity", expanded=not ncs):
                with st.form("nc_create", clear_on_submit=True):
                    project_label = st.selectbox("Project", project_labels)
                    project_id = project_map[project_label]
                    project_tests = rows(database_path,
                                         "SELECT id, test_code, description FROM tests WHERE project_id=? ORDER BY test_code",
                                         (project_id,))
                    test_labels = [f"{row['test_code']} · {row['description']}" for row in project_tests]
                    test_map = {label: row["id"] for label, row in zip(test_labels, project_tests)}
                    test_label = st.selectbox("Originating test", ["Not test-related", *test_labels])
                    components = rows(database_path,
                                      "SELECT id, name FROM components WHERE project_id=? ORDER BY name",
                                      (project_id,))
                    component_labels, component_map = choice_options(components)
                    component_label = st.selectbox("Component", ["Not specified", *component_labels])
                    supplier_label = st.selectbox("Supplier", ["Not specified", *supplier_labels])
                    description = st.text_area("Non-conformity description *")
                    detected = st.date_input("Detection date", value=date.today())
                    severity = st.selectbox("Severity", ["Critical", "Major", "Minor"])
                    containment = st.text_area("Containment measures")
                    submit = st.form_submit_button("Create non-conformity", type="primary")
                if submit:
                    try:
                        create_non_conformity(
                            database_path, project_id=project_id, description=description,
                            detected_date=date_value(detected), test_id=test_map.get(test_label),
                            component_id=component_map.get(component_label),
                            supplier_id=supplier_map.get(supplier_label), severity=severity,
                            containment=containment, username=user["username"],
                        )
                        st.success("Non-conformity recorded.")
                        st.rerun()
                    except Exception as error:
                        report_error(error)
        nc_labels = [f"{row['nc_code']} · {row['description'][:70]}" for row in ncs]
        if nc_labels and require_editor(can_edit):
            with st.expander("Update investigation / closure"):
                selected = st.selectbox("Non-conformity", nc_labels)
                nc = ncs[nc_labels.index(selected)]
                with st.form("nc_update"):
                    status = st.selectbox("Status", NC_STATUSES, index=NC_STATUSES.index(nc["status"]))
                    containment = st.text_area("Containment", value=nc["containment"] or "")
                    five_why = st.text_area("5 Why analysis", value=nc["five_why"] or "")
                    ishikawa = st.text_area("Ishikawa / fishbone analysis", value=nc["ishikawa"] or "")
                    correction = st.text_area("Immediate correction", value=nc["immediate_correction"] or "")
                    verification = st.text_area("Effectiveness verification", value=nc["effectiveness_verification"] or "")
                    verified = st.checkbox("Effectiveness verified", value=bool(nc["effectiveness_verified"]))
                    approver = st.text_input("Closure approver", value=nc["closure_approved_by"] or "")
                    submit = st.form_submit_button("Save investigation")
                if submit:
                    try:
                        update_non_conformity(
                            database_path, nc["id"], status=status, containment=containment,
                            five_why=five_why, ishikawa=ishikawa, immediate_correction=correction,
                            effectiveness_verification=verification, effectiveness_verified=verified,
                            closure_approved_by=approver, username=user["username"],
                        )
                        st.success("Non-conformity updated.")
                        st.rerun()
                    except Exception as error:
                        report_error(error)
    with tab_actions:
        filters = st.columns(5)
        owner_filter = filters[0].selectbox("Owner", ["All"] + sorted({a["owner"] for a in actions}))
        priority_filter = filters[1].selectbox("Priority", ["All", "Low", "Medium", "High", "Critical"])
        project_filter = filters[2].selectbox("Project", ["All", *project_labels])
        supplier_filter = filters[3].selectbox("Supplier", ["All", *supplier_labels])
        status_filter = filters[4].selectbox("Status", ["All", *ACTION_STATUSES])
        visible_actions = [a for a in actions
                           if (owner_filter == "All" or a["owner"] == owner_filter)
                           and (priority_filter == "All" or a["priority"] == priority_filter)
                           and (project_filter == "All" or a["project_id"] == project_map[project_filter])
                           and (supplier_filter == "All" or a["supplier_id"] == supplier_map[supplier_filter])
                           and (status_filter == "All" or a["status"] == status_filter)]
        show_rows(visible_actions, "No actions match these filters.")
        if project_labels and require_editor(can_edit):
            with st.expander("Create action"):
                with st.form("action_create", clear_on_submit=True):
                    project_label = st.selectbox("Project", project_labels, key="action_project")
                    project_id = project_map[project_label]
                    supplier_label = st.selectbox("Supplier", ["Not assigned", *supplier_labels])
                    nc_candidates = [nc for nc in ncs if nc["project_id"] == project_id]
                    nc_labels_local = [f"{nc['nc_code']} · {nc['description'][:60]}" for nc in nc_candidates]
                    nc_map = {label: nc["id"] for label, nc in zip(nc_labels_local, nc_candidates)}
                    nc_label = st.selectbox("Linked non-conformity", ["None", *nc_labels_local])
                    description = st.text_input("Action description *")
                    owner = st.text_input("Responsible person *")
                    due_date = st.date_input("Due date", value=date.today())
                    priority = st.selectbox("Priority", ["Low", "Medium", "High", "Critical"])
                    source = st.selectbox("Origin", ["Project review", "Test", "Supplier visit", "Non-conformity"])
                    mandatory = st.checkbox("Mandatory for final validation")
                    submit = st.form_submit_button("Create action")
                if submit:
                    try:
                        create_action(
                            database_path, project_id=project_id, description=description,
                            owner=owner, due_date=date_value(due_date), priority=priority,
                            supplier_id=supplier_map.get(supplier_label), nc_id=nc_map.get(nc_label),
                            source_type=source, mandatory=mandatory, username=user["username"],
                        )
                        st.success("Action created.")
                        st.rerun()
                    except Exception as error:
                        report_error(error)
        action_labels = [f"{action['action_code']} · {action['description'][:70]}" for action in actions]
        if action_labels and require_editor(can_edit):
            with st.expander("Update action status"):
                selected = st.selectbox("Action", action_labels)
                action = actions[action_labels.index(selected)]
                with st.form("action_update"):
                    status = st.selectbox("Status", ACTION_STATUSES,
                                          index=ACTION_STATUSES.index(action["status"]))
                    evidence = st.text_area("Evidence / closure reference", value=action["evidence"] or "")
                    effectiveness = st.text_area("Effectiveness verification",
                                                 value=action["effectiveness_verification"] or "")
                    effectiveness_verified = st.checkbox(
                        "Effectiveness verified", value=bool(action["effectiveness_verified"])
                    )
                    submit = st.form_submit_button("Save action")
                if submit:
                    try:
                        update_action(database_path, action["id"], status=status,
                                      evidence=evidence, effectiveness_verification=effectiveness,
                                      effectiveness_verified=effectiveness_verified,
                                      username=user["username"])
                        st.success("Action updated.")
                        st.rerun()
                    except Exception as error:
                        report_error(error)