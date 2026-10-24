from datetime import date

import streamlit as st

from piv_manager.reports import REPORTS, build_report, export_csv, export_excel
from piv_manager.ui_common import choice_options, report_error, rows


def render(database_path):
    st.title("Reports & exports")
    st.caption("Filtered operational extracts · CSV and Excel")
    projects = rows(database_path, "SELECT id, name FROM projects WHERE archived=0 ORDER BY name")
    labels, project_map = choice_options(projects)
    report_name = st.selectbox("Report", list(REPORTS))
    project_label = st.selectbox("Project filter", ["All projects", *labels])
    try:
        frame = build_report(database_path, report_name, project_map.get(project_label))
        if not frame.empty:
            filter_columns = [column for column in ("status", "severity", "priority", "supplier")
                              if column in frame.columns and frame[column].notna().any()]
            controls = st.columns(max(1, len(filter_columns)))
            for index, column in enumerate(filter_columns):
                choices = sorted(frame[column].dropna().astype(str).unique())
                selected = controls[index].multiselect(f"Filter {column}", choices, default=choices)
                frame = frame[frame[column].astype(str).isin(selected)]
            date_column = next((column for column in ("due_date", "planned_end", "detected_date")
                                if column in frame.columns), None)
            if date_column:
                range_col, _ = st.columns([1, 2])
                date_filter = range_col.date_input(f"{date_column} range", value=())
                if len(date_filter) == 2:
                    dates = frame[date_column].astype(str)
                    frame = frame[(dates >= date_filter[0].isoformat()) &
                                  (dates <= date_filter[1].isoformat())]
        st.metric("Records", len(frame))
        st.dataframe(frame, width="stretch", hide_index=True)
        stem = report_name.lower().replace(" ", "_").replace("/", "_")
        csv, excel = st.columns(2)
        csv.download_button("Download CSV", export_csv(frame), f"{stem}.csv", "text/csv")
        excel.download_button(
            "Download Excel", export_excel(frame, report_name), f"{stem}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as error:
        report_error(error)