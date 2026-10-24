from datetime import date

import streamlit as st

from piv_manager.services import (
    create_sample,
    create_supplier,
    create_supplier_contact,
    create_supplier_visit,
    list_suppliers,
    update_sample_delivery,
    update_supplier,
)
from piv_manager.ui_common import choice_options, date_value, report_error, require_editor, rows, show_rows


def render(database_path, user, can_edit):
    st.title("Suppliers & samples")
    st.caption("Supplier coordination · Deliveries · Visits and findings")
    supplier_data = list_suppliers(database_path)
    show_rows(supplier_data)
    tabs = st.tabs(["Supplier", "Samples & delivery", "Supplier visits", "Performance"])
    with tabs[0]:
        with st.expander("Create or edit supplier", expanded=not supplier_data):
            if require_editor(can_edit):
                existing_labels, existing_map = choice_options(supplier_data)
                selected = st.selectbox("Supplier record", ["Create new", *existing_labels])
                existing = next((row for row in supplier_data if row["id"] == existing_map.get(selected)), None)
                with st.form("supplier_form"):
                    name = st.text_input("Supplier name *", value=existing["name"] if existing else "")
                    site = st.text_input("Site", value=existing["site"] if existing else "")
                    email = st.text_input("Contact email", value=existing["email"] if existing else "")
                    phone = st.text_input("Contact phone", value=existing["phone"] if existing else "")
                    submit = st.form_submit_button("Save supplier")
                if submit:
                    try:
                        if existing:
                            update_supplier(database_path, existing["id"], name=name, site=site,
                                            email=email, phone=phone, username=user["username"])
                        else:
                            create_supplier(database_path, name=name, site=site,
                                            email=email, phone=phone, username=user["username"])
                        st.success("Supplier saved.")
                        st.rerun()
                    except Exception as error:
                        report_error(error)
        supplier_labels, supplier_map = choice_options(supplier_data)
        if supplier_labels and require_editor(can_edit):
            with st.expander("Add supplier contact"):
                with st.form("supplier_contact", clear_on_submit=True):
                    supplier_label = st.selectbox("Supplier", supplier_labels, key="contact_supplier")
                    contact_name = st.text_input("Contact name *")
                    contact_role = st.text_input("Role")
                    contact_email = st.text_input("Email")
                    contact_phone = st.text_input("Phone")
                    primary = st.checkbox("Primary contact")
                    submit = st.form_submit_button("Add contact")
                if submit:
                    try:
                        create_supplier_contact(database_path, supplier_id=supplier_map[supplier_label],
                                                name=contact_name, role=contact_role,
                                                email=contact_email, phone=contact_phone,
                                                is_primary=primary, username=user["username"])
                        st.success("Supplier contact added.")
                        st.rerun()
                    except Exception as error:
                        report_error(error)
        show_rows(rows(database_path, """SELECT s.name AS supplier, c.name AS contact,
            c.role, c.email, c.phone, c.is_primary FROM supplier_contacts c
            JOIN suppliers s ON s.id=c.supplier_id ORDER BY s.name, c.is_primary DESC, c.name"""),
            "No supplier contacts recorded.")
    active_projects = rows(database_path, "SELECT id, name FROM projects WHERE archived=0 ORDER BY name")
    project_labels, project_map = choice_options(active_projects)
    supplier_labels, supplier_map = choice_options(supplier_data)
    with tabs[1]:
        samples = rows(database_path, """SELECT sm.*, p.name AS project, s.name AS supplier,
            c.name AS component FROM samples sm JOIN projects p ON p.id=sm.project_id
            LEFT JOIN suppliers s ON s.id=sm.supplier_id LEFT JOIN components c ON c.id=sm.component_id
            ORDER BY COALESCE(sm.required_date, sm.committed_date)""")
        show_rows(samples, "No sample requirements have been recorded.")
        if project_labels and require_editor(can_edit):
            with st.expander("Add sample requirement", expanded=not samples):
                with st.form("sample_create", clear_on_submit=True):
                    project_label = st.selectbox("Project", project_labels)
                    project_id = project_map[project_label]
                    components = rows(database_path, "SELECT id, name FROM components WHERE project_id=? ORDER BY name",
                                      (project_id,))
                    component_labels, component_map = choice_options(components)
                    component_label = st.selectbox("Component", ["Not specified", *component_labels])
                    supplier_label = st.selectbox("Supplier", ["Not specified", *supplier_labels])
                    description = st.text_input("Sample / prototype description *")
                    required_quantity = st.number_input("Required quantity", min_value=0, value=1, step=1)
                    required_date = st.date_input("Required delivery date", value=None)
                    committed_date = st.date_input("Supplier committed date", value=None)
                    submit = st.form_submit_button("Record requirement")
                if submit:
                    try:
                        create_sample(database_path, project_id=project_id, description=description,
                                      required_quantity=int(required_quantity),
                                      required_date=date_value(required_date),
                                      committed_date=date_value(committed_date),
                                      supplier_id=supplier_map.get(supplier_label),
                                      component_id=component_map.get(component_label), username=user["username"])
                        st.success("Sample requirement recorded.")
                        st.rerun()
                    except Exception as error:
                        report_error(error)
        sample_labels = [f"#{row['id']} · {row['description']} · {row['project']}" for row in samples]
        if sample_labels and require_editor(can_edit):
            with st.expander("Record receipt / inspection"):
                selected = st.selectbox("Sample record", sample_labels)
                sample = samples[sample_labels.index(selected)]
                with st.form("sample_delivery"):
                    committed = st.date_input("Committed date", value=None)
                    received_date = st.date_input("Actual receipt date", value=None)
                    received = st.number_input("Received quantity", min_value=0,
                                               value=int(sample["received_quantity"]), step=1)
                    conformity = st.selectbox("Conformity", ["Unknown", "Conforming", "Non-conforming", "Missing"])
                    notes = st.text_area("Inspection notes", value=sample["notes"] or "")
                    submit = st.form_submit_button("Update delivery")
                if submit:
                    try:
                        update_sample_delivery(database_path, sample["id"],
                                               committed_date=date_value(committed),
                                               actual_receipt_date=date_value(received_date),
                                               received_quantity=int(received), conformity=conformity,
                                               notes=notes, username=user["username"])
                        st.success("Delivery and conformity updated.")
                        st.rerun()
                    except Exception as error:
                        report_error(error)
    with tabs[2]:
        if supplier_labels and require_editor(can_edit):
            with st.form("supplier_visit", clear_on_submit=True):
                supplier_label = st.selectbox("Supplier", supplier_labels)
                project_label = st.selectbox("Project", ["Not linked", *project_labels])
                visit_date = st.date_input("Visit date", value=date.today())
                purpose = st.text_input("Purpose *")
                visitors = st.text_input("Visitors")
                findings = st.text_area("Inspection findings")
                submit = st.form_submit_button("Record visit")
            if submit:
                try:
                    create_supplier_visit(database_path, supplier_id=supplier_map[supplier_label],
                                          project_id=project_map.get(project_label),
                                          visit_date=date_value(visit_date), purpose=purpose,
                                          visitors=visitors, findings=findings, username=user["username"])
                    st.success("Supplier visit recorded.")
                    st.rerun()
                except Exception as error:
                    report_error(error)
        show_rows(rows(database_path, """SELECT v.visit_date, s.name AS supplier, p.name AS project,
            v.purpose, v.visitors, v.findings FROM supplier_visits v
            JOIN suppliers s ON s.id=v.supplier_id LEFT JOIN projects p ON p.id=v.project_id
            ORDER BY v.visit_date DESC"""))
    with tabs[3]:
        performance = rows(database_path, """SELECT s.name AS supplier,
            (SELECT COUNT(*) FROM samples sm WHERE sm.supplier_id=s.id) AS deliveries,
            (SELECT CASE WHEN COUNT(*)=0 THEN NULL ELSE ROUND(100.0 * SUM(
                CASE WHEN sm.actual_receipt_date IS NOT NULL AND sm.actual_receipt_date<=
                    COALESCE(sm.committed_date, sm.required_date) THEN 1 ELSE 0 END) / COUNT(*), 1) END
                FROM samples sm WHERE sm.supplier_id=s.id) AS on_time_rate_pct,
            (SELECT COUNT(*) FROM samples sm WHERE sm.supplier_id=s.id
                AND sm.actual_receipt_date IS NOT NULL
                AND sm.actual_receipt_date<=COALESCE(sm.committed_date, sm.required_date)) AS on_time,
            (SELECT CASE WHEN COUNT(*)=0 THEN NULL ELSE ROUND(100.0 * SUM(
                CASE WHEN sm.conformity='Conforming' AND sm.received_quantity>=sm.required_quantity
                    THEN 1 ELSE 0 END) / COUNT(*), 1) END
                FROM samples sm WHERE sm.supplier_id=s.id) AS conformity_rate_pct,
            (SELECT COUNT(*) FROM samples sm WHERE sm.supplier_id=s.id
                AND sm.conformity='Conforming' AND sm.received_quantity>=sm.required_quantity) AS conforming,
            (SELECT COUNT(*) FROM actions a WHERE a.supplier_id=s.id) AS actions,
            (SELECT COUNT(*) FROM actions a WHERE a.supplier_id=s.id AND a.status='Closed') AS closed_actions,
            (SELECT CASE WHEN COUNT(*)=0 THEN NULL ELSE ROUND(100.0 * SUM(
                CASE WHEN a.status='Closed' THEN 1 ELSE 0 END) / COUNT(*), 1) END
                FROM actions a WHERE a.supplier_id=s.id) AS action_closure_rate_pct
            FROM suppliers s ORDER BY s.name""")
        show_rows(performance, "Supplier performance will appear after deliveries and actions are recorded.")