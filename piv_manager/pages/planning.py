from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from piv_manager.services import create_milestone, reschedule_test, update_milestone
from piv_manager.ui_common import choice_options, date_value, report_error, require_editor, rows, show_rows


def render(database_path, user, can_edit):
    st.title("Planning & milestones")
    st.caption("APQP milestones · Test schedule · Baseline versus current plan")
    projects = rows(database_path, "SELECT id, name FROM projects WHERE archived=0 ORDER BY name")
    project_labels, project_map = choice_options(projects)
    if not project_labels:
        st.info("Create a project to start planning.")
        return
    selected_project = st.selectbox("Project scope", project_labels)
    project_id = project_map[selected_project]
    milestones = rows(database_path,
                      "SELECT * FROM project_milestones WHERE project_id=? ORDER BY planned_date",
                      (project_id,))
    tests = rows(database_path,
                 "SELECT * FROM tests WHERE project_id=? ORDER BY COALESCE(planned_start, planned_end)",
                 (project_id,))
    gantt_rows = []
    for test in tests:
        if test["planned_start"] or test["planned_end"]:
            end = date.fromisoformat(test["planned_end"] or test["planned_start"])
            start = date.fromisoformat(test["planned_start"] or test["planned_end"])
            gantt_rows.append({"Activity": f"{test['test_code']} · {test['description']}",
                               "Start": start, "Finish": max(start + timedelta(days=1), end),
                               "Type": "Test", "Status": test["status"]})
    for milestone in milestones:
        planned = date.fromisoformat(milestone["planned_date"])
        gantt_rows.append({"Activity": f"APQP · {milestone['name']}", "Start": planned,
                           "Finish": planned + timedelta(days=1), "Type": "Milestone",
                           "Status": milestone["status"]})
    if gantt_rows:
        chart_data = pd.DataFrame(gantt_rows)
        fig = px.timeline(chart_data, x_start="Start", x_end="Finish", y="Activity",
                          color="Status", hover_data=["Type"])
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(height=max(300, min(650, len(gantt_rows) * 34)),
                          margin=dict(l=0, r=0, t=10, b=0), xaxis_title="Planned schedule")
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("Add planned test dates or milestones to populate the schedule.")

    today = date.today().isoformat()
    schedule = []
    for test in tests:
        if test["planned_end"]:
            schedule.append({"Type": "Test", "Activity": test["description"],
                             "Baseline start": test["original_planned_start"],
                             "Baseline end": test["original_planned_end"],
                             "Current start": test["planned_start"], "Current end": test["planned_end"],
                             "Actual": test["actual_test_date"],
                             "Risk": ("Critical-path risk" if test["mandatory"] and
                                      (test["planned_end"] < today and test["status"] not in ("Passed", "Failed")
                                       or test["status"] == "Blocked") else
                                      "At risk" if test["planned_end"] < today and
                                      test["status"] not in ("Passed", "Failed") else "On track")})
    for milestone in milestones:
        schedule.append({"Type": "Milestone", "Activity": milestone["name"],
                         "Baseline start": milestone["original_planned_date"] or milestone["planned_date"],
                         "Baseline end": milestone["original_planned_date"] or milestone["planned_date"],
                         "Current start": milestone["planned_date"], "Current end": milestone["planned_date"],
                         "Actual": milestone["actual_date"],
                         "Risk": ("Critical-path risk" if milestone["mandatory"] and
                                  (milestone["planned_date"] < today and milestone["status"] != "Complete"
                                   or milestone["status"] == "Blocked") else
                                  "At risk" if milestone["planned_date"] < today and
                                  milestone["status"] != "Complete" else "On track")})
    st.markdown("#### Planned versus actual")
    if schedule:
        st.dataframe(pd.DataFrame(schedule), width="stretch", hide_index=True)
    else:
        st.info("No dated activities are currently recorded.")

    tabs = st.tabs(["Add milestone", "Update milestone", "Reschedule test"])
    with tabs[0]:
        if require_editor(can_edit):
            with st.form("milestone_create", clear_on_submit=True):
                name = st.text_input("Milestone name *")
                category = st.selectbox("Category", ["APQP", "PIV", "Design review", "Validation review", "Production"])
                planned = st.date_input("Planned date", value=None)
                owner = st.text_input("Owner")
                mandatory = st.checkbox("Mandatory", value=True)
                submit = st.form_submit_button("Add milestone")
            if submit:
                try:
                    create_milestone(database_path, project_id=project_id, name=name,
                                     planned_date=date_value(planned), category=category,
                                     owner=owner, mandatory=mandatory)
                    st.success("Milestone created.")
                    st.rerun()
                except Exception as error:
                    report_error(error)
    with tabs[1]:
        labels = [f"#{item['id']} · {item['name']} · {item['planned_date']}" for item in milestones]
        if labels and require_editor(can_edit):
            selected = st.selectbox("Milestone", labels)
            milestone = milestones[labels.index(selected)]
            with st.form("milestone_update"):
                status = st.selectbox("Status", ["Planned", "In Progress", "Complete", "Blocked"],
                                      index=["Planned", "In Progress", "Complete", "Blocked"].index(milestone["status"]))
                planned = st.date_input("Current planned date",
                                        value=date.fromisoformat(milestone["planned_date"]))
                actual = st.date_input("Actual completion date", value=None)
                reason = st.text_input("Schedule change reason")
                submit = st.form_submit_button("Update milestone")
            if submit:
                try:
                    update_milestone(database_path, milestone["id"], status=status,
                                     planned_date=date_value(planned), actual_date=date_value(actual),
                                     reason=reason, username=user["username"])
                    st.success("Milestone updated; baseline date retained.")
                    st.rerun()
                except Exception as error:
                    report_error(error)
    with tabs[2]:
        dated_tests = [test for test in tests if test["status"] not in ("Passed", "Failed")]
        labels = [f"{item['test_code']} · {item['description']}" for item in dated_tests]
        if labels and require_editor(can_edit):
            selected = st.selectbox("Test to reschedule", labels)
            test = dated_tests[labels.index(selected)]
            with st.form("test_reschedule"):
                start = st.date_input("Revised planned start",
                                      value=date.fromisoformat(test["planned_start"]) if test["planned_start"] else None)
                finish = st.date_input("Revised planned end",
                                       value=date.fromisoformat(test["planned_end"]) if test["planned_end"] else None)
                reason = st.text_input("Schedule change reason", key="test_schedule_reason")
                submit = st.form_submit_button("Save revised schedule")
            if submit:
                try:
                    reschedule_test(database_path, test["id"], planned_start=date_value(start),
                                    planned_end=date_value(finish), reason=reason,
                                    username=user["username"])
                    st.success("Test rescheduled; original planned dates retained.")
                    st.rerun()
                except Exception as error:
                    report_error(error)
    st.markdown("#### Schedule change history")
    show_rows(rows(database_path, """SELECT entity_type, entity_id, changed_at, changed_by,
        previous_start, previous_end, new_start, new_end, reason FROM schedule_history
        WHERE entity_id IN (SELECT id FROM tests WHERE project_id=?)
           OR entity_id IN (SELECT id FROM project_milestones WHERE project_id=?)
        ORDER BY changed_at DESC""", (project_id, project_id)), "No schedule changes recorded.")