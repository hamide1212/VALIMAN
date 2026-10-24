from datetime import date

import streamlit as st

from piv_manager.services import (
    archive_project,
    create_component,
    create_project,
    list_projects,
    list_suppliers,
    update_project,
)
from piv_manager.ui_common import choice_options, date_value, report_error, require_editor, rows, show_rows


def render(database_path, user, can_edit):
    st.title("Projects & PIV")
    st.caption("Programs, components, revisions, owners and validation targets")
    projects = list_projects(database_path, include_archived=True)
    search_col, status_col = st.columns([2, 1])
    project_search = search_col.text_input("Search project / program / pilot")
    project_status = status_col.selectbox("Project status", ["All", "Active", "On Hold", "Completed", "Archived"])
    visible_projects = [project for project in projects
                       if (project_status == "All" or project["status"] == project_status)
                       and (not project_search or project_search.casefold() in " ".join(
                           str(project[key] or "") for key in
                           ("project_code", "name", "vehicle_program", "validation_pilot")
                       ).casefold())]
    show_rows(visible_projects, "No projects match these filters.")
    tabs = st.tabs(["Project", "Component", "Edit / archive"])
    with tabs[0]:
        if require_editor(can_edit):
            with st.form("create_project", clear_on_submit=True):
                name = st.text_input("Project name *")
                vehicle = st.text_input("Vehicle program")
                manager, pilot = st.columns(2)
                project_manager = manager.text_input("Project manager")
                validation_pilot = pilot.text_input("Validation pilot")
                start, target = st.columns(2)
                start_date = start.date_input("Start date", value=None)
                target_date = target.date_input("Target validation date", value=None)
                phase = st.selectbox("Phase", ["Concept", "Design", "Validation", "Production", "Closed"])
                if st.form_submit_button("Create project", type="primary"):
                    try:
                        create_project(
                            database_path, name=name, vehicle_program=vehicle,
                            project_manager=project_manager, validation_pilot=validation_pilot,
                            start_date=date_value(start_date), target_validation_date=date_value(target_date),
                            phase=phase, username=user["username"],
                        )
                        st.success("Project created.")
                        st.rerun()
                    except Exception as error:
                        report_error(error)
    with tabs[1]:
        project_rows = rows(database_path, "SELECT id, name FROM projects WHERE archived=0 ORDER BY name")
        supplier_rows = list_suppliers(database_path)
        project_labels, project_map = choice_options(project_rows)
        supplier_labels, supplier_map = choice_options(supplier_rows)
        if not project_labels:
            st.info("Create a project before adding components.")
        elif require_editor(can_edit):
            with st.form("create_component", clear_on_submit=True):
                project_label = st.selectbox("Project", project_labels)
                name = st.text_input("Component name *")
                part_number, revision = st.columns(2)
                part = part_number.text_input("Part number *")
                rev = revision.text_input("Part revision *")
                supplier_label = st.selectbox("Supplier", ["Not assigned", *supplier_labels])
                if st.form_submit_button("Add component"):
                    try:
                        create_component(
                            database_path, project_id=project_map[project_label], name=name,
                            part_number=part, part_revision=rev,
                            supplier_id=supplier_map.get(supplier_label),
                        )
                        st.success("Component added.")
                        st.rerun()
                    except Exception as error:
                        report_error(error)
        show_rows(rows(database_path, """SELECT p.name AS project, c.name AS component,
            c.part_number, c.part_revision, s.name AS supplier FROM components c
            JOIN projects p ON p.id=c.project_id LEFT JOIN suppliers s ON s.id=c.supplier_id
            ORDER BY p.name, c.part_number"""))
    with tabs[2]:
        active_projects = rows(database_path, "SELECT * FROM projects WHERE archived=0 ORDER BY name")
        labels, project_map = choice_options(active_projects)
        if labels and require_editor(can_edit):
            selected = st.selectbox("Select project to edit", labels, key="edit_project_select")
            project_id = project_map[selected]
            project = next(row for row in active_projects if row["id"] == project_id)
            with st.form("edit_project"):
                name = st.text_input("Project name", value=project["name"])
                vehicle = st.text_input("Vehicle program", value=project["vehicle_program"] or "")
                project_manager = st.text_input("Project manager", value=project["project_manager"] or "")
                validation_pilot = st.text_input("Validation pilot", value=project["validation_pilot"] or "")
                start, target = st.columns(2)
                start_date = start.date_input(
                    "Start date",
                    value=date.fromisoformat(project["start_date"]) if project["start_date"] else None,
                )
                target_date = target.date_input("Target validation date",
                                                value=date.fromisoformat(project["target_validation_date"])
                                                if project["target_validation_date"] else None)
                completion = st.date_input("Actual completion date",
                                           value=date.fromisoformat(project["actual_completion_date"])
                                           if project["actual_completion_date"] else None)
                phase = st.selectbox("Phase", ["Concept", "Design", "Validation", "Production", "Closed"],
                                     index=["Concept", "Design", "Validation", "Production", "Closed"].index(project["phase"]))
                status = st.selectbox("Status", ["Active", "On Hold", "Completed"],
                                      index=["Active", "On Hold", "Completed"].index(project["status"]))
                submitted = st.form_submit_button("Save project")
            if submitted:
                try:
                    update_project(database_path, project_id, name=name, vehicle_program=vehicle,
                                   project_manager=project_manager, validation_pilot=validation_pilot,
                                   start_date=date_value(start_date),
                                   target_validation_date=date_value(target_date),
                                   phase=phase, status=status,
                                   actual_completion_date=date_value(completion),
                                   username=user["username"])
                    st.success("Project updated.")
                    st.rerun()
                except Exception as error:
                    report_error(error)
            confirm = st.checkbox("Confirm archive; project records will be retained")
            if st.button("Archive project", disabled=not confirm):
                try:
                    archive_project(database_path, project_id, user["username"])
                    st.success("Project archived.")
                    st.rerun()
                except Exception as error:
                    report_error(error)
        elif not labels:
            st.info("No active projects to edit.")