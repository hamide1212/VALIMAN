from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from piv_manager.reports import build_report
from piv_manager.services import get_dashboard_data, get_readiness
from piv_manager.ui_common import choice_options, rows, show_rows


def render(database_path):
    st.title("Validation cockpit")
    st.caption("PIV control room · Pilotage validation")
    project_rows = rows(database_path, "SELECT id, name FROM projects WHERE archived=0 ORDER BY name")
    supplier_rows = rows(database_path, "SELECT id, name FROM suppliers WHERE archived=0 ORDER BY name")
    component_rows = rows(database_path, "SELECT id, name FROM components ORDER BY name")
    project_labels, projects = choice_options(project_rows)
    supplier_labels, suppliers = choice_options(supplier_rows)
    component_labels, components = choice_options(component_rows)
    with st.container(border=True):
        col1, col2, col3, col4 = st.columns([1.2, 1.2, 1.2, 1.4])
        selected_project = col1.selectbox("Project", ["All projects", *project_labels])
        selected_supplier = col2.selectbox("Supplier", ["All suppliers", *supplier_labels])
        selected_component = col3.selectbox("Component", ["All components", *component_labels])
        date_range = col4.date_input("Activity date range", value=())
    filters = {
        "project_id": projects.get(selected_project),
        "supplier_id": suppliers.get(selected_supplier),
        "component_id": components.get(selected_component),
        "start_date": date_range[0].isoformat() if len(date_range) == 2 else None,
        "end_date": date_range[1].isoformat() if len(date_range) == 2 else None,
    }
    data = get_dashboard_data(database_path, **filters)
    metrics = [
        ("Active projects", data["active_projects"]),
        ("Tests passed", data["completed_tests"]),
        ("Tests pending", data["pending_tests"]),
        ("Tests overdue", data["overdue_tests"]),
        ("Open non-conformities", data["open_non_conformities"]),
        ("Overdue actions", data["overdue_actions"]),
    ]
    metric_columns = st.columns(3)
    for index, (label, value) in enumerate(metrics):
        with metric_columns[index % 3]:
            st.metric(label, f"{value:,}")
    st.markdown("#### Test status · Statut des essais")
    if data["test_status"]:
        chart_data = pd.DataFrame([dict(row) for row in data["test_status"]])
        colors = {
            "Passed": "#198754", "Failed": "#c84040", "Blocked": "#c98216",
            "Retest Required": "#c98216", "In Progress": "#2687a8", "Ready": "#65a77c",
            "Planned": "#7b8792", "Not Planned": "#aab3ba",
        }
        fig = px.bar(chart_data, x="status", y="count", color="status", text="count",
                     color_discrete_map=colors)
        fig.update_layout(showlegend=False, margin=dict(l=0, r=0, t=8, b=0), height=280,
                          xaxis_title=None, yaxis_title="Tests")
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No test records match these filters.")

    left, right = st.columns([1.2, 1])
    with left:
        st.markdown("#### Upcoming deadlines · Échéances")
        show_rows(data["upcoming"], "No activities due in the next 30 days.")
    with right:
        st.markdown("#### Critical issues · Points critiques")
        show_rows(data["critical_issues"], "No open critical or major non-conformities.")

    st.markdown("#### Final validation status · Validation finale")
    status_rows = rows(
        database_path,
        """SELECT p.id, p.project_code, p.name AS project,
           (SELECT decision FROM final_approval_history f WHERE f.project_id=p.id
            ORDER BY decision_date DESC, id DESC LIMIT 1) AS latest_decision
           FROM projects p WHERE p.archived=0 ORDER BY p.name""",
    )
    validation_rows = []
    for item in status_rows:
        readiness = get_readiness(database_path, item["id"]) if "id" in item.keys() else None
        validation_rows.append({
            "Project": item["project"],
            "Latest decision": item["latest_decision"] or "Not Ready",
            "Readiness": "Ready for review" if readiness and readiness["ready"] else "Not ready",
            "Open criteria": len(readiness["pending"]) if readiness else 0,
        })
    if validation_rows:
        st.dataframe(pd.DataFrame(validation_rows), width="stretch", hide_index=True)
    else:
        st.info("Create a project to begin validation tracking.")
