import streamlit as st

from piv_manager.services import (
    create_test,
    update_test_status,
)
from piv_manager.ui_common import choice_options, date_value, report_error, require_editor, rows, show_rows


TEST_CATEGORIES = [
    "Component test", "Bench test", "Laboratory test", "Environmental test",
    "Durability test", "Vehicle test",
]
TEST_STATUSES = [
    "Not Planned", "Planned", "Ready", "In Progress", "Passed", "Failed", "Blocked", "Retest Required",
]


def render(database_path, user, can_edit):
    st.title("Validation tests")
    st.caption("Test plans, results, retest lineage and preserved status history")
    tests = rows(database_path, """SELECT t.*, p.name AS project, c.name AS component,
        s.name AS supplier FROM tests t JOIN projects p ON p.id=t.project_id
        LEFT JOIN components c ON c.id=t.component_id LEFT JOIN suppliers s ON s.id=t.supplier_id
        ORDER BY t.updated_at DESC""")
    search_col, status_col, project_col = st.columns([2, 1, 1])
    search = search_col.text_input("Search test / requirement / report")
    statuses = ["All", *sorted({item["status"] for item in tests})]
    status_filter = status_col.selectbox("Status", statuses)
    project_names = ["All", *sorted({item["project"] for item in tests})]
    project_filter = project_col.selectbox("Project", project_names)
    visible_tests = [item for item in tests
                     if (status_filter == "All" or item["status"] == status_filter)
                     and (project_filter == "All" or item["project"] == project_filter)
                     and (not search or search.casefold() in " ".join(
                         str(item[key] or "") for key in
                         ("test_code", "description", "validation_requirement", "report_reference")
                     ).casefold())]
    show_rows(visible_tests, "No tests match these filters.")
    create_tab, result_tab, history_tab = st.tabs(["Plan test", "Record result", "Test history"])
    projects = rows(database_path, "SELECT id, name FROM projects WHERE archived=0 ORDER BY name")
    project_labels, project_map = choice_options(projects)
    suppliers = rows(database_path, "SELECT id, name FROM suppliers WHERE archived=0 ORDER BY name")
    supplier_labels, supplier_map = choice_options(suppliers)
    if not project_labels:
        st.info("Create a project before planning tests.")
        return
    with create_tab:
        if require_editor(can_edit):
            with st.form("create_test", clear_on_submit=True):
                project_label = st.selectbox("Project", project_labels)
                project_id = project_map[project_label]
                components = rows(database_path,
                                  "SELECT id, name, part_number FROM components WHERE project_id=? ORDER BY name",
                                  (project_id,))
                component_labels, component_map = choice_options(components, "name")
                component_label = st.selectbox("Component", ["Not specified", *component_labels])
                supplier_label = st.selectbox("Supplier", ["Not specified", *supplier_labels])
                original_tests = rows(database_path,
                                      "SELECT id, test_code, description FROM tests WHERE project_id=? ORDER BY test_code",
                                      (project_id,))
                original_labels = [f"{row['test_code']} · {row['description']}" for row in original_tests]
                original_map = {label: row["id"] for label, row in zip(original_labels, original_tests)}
                original_label = st.selectbox("Original test (for retest)", ["New test", *original_labels])
                description = st.text_input("Test description *")
                requirement = st.text_area("Validation requirement")
                category = st.selectbox("Test category", TEST_CATEGORIES)
                owner = st.text_input("Test owner")
                location = st.text_input("Test location")
                laboratory = st.text_input("Laboratory")
                start, end = st.columns(2)
                planned_start = start.date_input("Planned start", value=None)
                planned_end = end.date_input("Planned end", value=None)
                quantity, mandatory = st.columns(2)
                sample_quantity = quantity.number_input("Sample quantity", min_value=0, value=1, step=1)
                is_mandatory = mandatory.checkbox("Mandatory for final validation", value=True)
                sample_available = st.checkbox("Required samples available")
                required_documents = st.text_area("Required documents")
                acceptance = st.text_area("Acceptance criteria")
                if st.form_submit_button("Create test plan", type="primary"):
                    try:
                        create_test(
                            database_path, project_id=project_id, description=description,
                            category=category, component_id=component_map.get(component_label),
                            supplier_id=supplier_map.get(supplier_label),
                            original_test_id=original_map.get(original_label),
                            validation_requirement=requirement, test_owner=owner,
                            location=location, laboratory=laboratory,
                            required_documents=required_documents, sample_available=sample_available,
                            planned_start=date_value(planned_start), planned_end=date_value(planned_end),
                            sample_quantity=int(sample_quantity), acceptance_criteria=acceptance,
                            mandatory=is_mandatory, username=user["username"],
                        )
                        st.success("Test plan created.")
                        st.rerun()
                    except Exception as error:
                        report_error(error)
    with result_tab:
        test_labels = [f"{row['test_code']} · {row['description']}" for row in tests]
        test_map = {label: row["id"] for label, row in zip(test_labels, tests)}
        if test_labels and require_editor(can_edit):
            with st.form("update_test_result"):
                selected = st.selectbox("Test", test_labels)
                current = next(row for row in tests if row["id"] == test_map[selected])
                status = st.selectbox("Test status", TEST_STATUSES, index=TEST_STATUSES.index(current["status"]))
                result = st.text_input("Result", value=current["result"] or "")
                actual_date = st.date_input("Actual test date", value=None)
                report = st.text_input("Report reference", value=current["report_reference"] or "")
                sample_available = st.checkbox("Sample available", value=bool(current["sample_available"]))
                disposition = st.text_area("Justified disposition (required if failed without NC)",
                                           value=current["justified_disposition"] or "")
                comments = st.text_area("Comments", value=current["comments"] or "")
                submitted = st.form_submit_button("Save test result")
            if submitted:
                try:
                    update_test_status(
                        database_path, test_map[selected], status=status, result=result,
                        justified_disposition=disposition, actual_test_date=date_value(actual_date),
                        report_reference=report, comments=comments, sample_available=sample_available,
                        username=user["username"],
                    )
                    st.success("Test result saved to history.")
                    st.rerun()
                except Exception as error:
                    report_error(error)
        elif not test_labels:
            st.info("No test plans have been created.")
    with history_tab:
        if test_labels:
            selected = st.selectbox("Test history", test_labels, key="history_test")
            test_id = test_map[selected]
            show_rows(rows(database_path,
                           "SELECT changed_at, changed_by, previous_status, new_status, result, notes "
                           "FROM test_history WHERE test_id=? ORDER BY id DESC", (test_id,)))