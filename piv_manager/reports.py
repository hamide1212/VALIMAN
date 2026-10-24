"""Data-backed report generation and spreadsheet serialization."""

from __future__ import annotations

from datetime import date
from io import BytesIO, StringIO
from pathlib import Path

import pandas as pd

from piv_manager.db import transaction
from piv_manager.services import get_readiness


REPORTS = {
    "Project validation summary": "summary",
    "Detailed PIV tracking": "tracking",
    "Test status and results": "tests",
    "Supplier delivery and conformity": "suppliers",
    "Open non-conformities": "ncs",
    "Overdue actions": "actions",
    "Final validation readiness": "readiness",
}


def build_report(database_path: str | Path, report_name: str,
                 project_id: int | None = None) -> pd.DataFrame:
    if report_name not in REPORTS:
        raise ValueError("Unknown report type.")
    clauses = "WHERE p.archived=0"
    parameters: tuple[object, ...] = ()
    if project_id:
        clauses += " AND p.id=?"
        parameters = (project_id,)
    with transaction(database_path) as connection:
        if report_name == "Project validation summary":
            query = f"""SELECT p.project_code, p.name AS project, p.vehicle_program,
                p.phase, p.status, p.target_validation_date,
                COUNT(DISTINCT t.id) AS total_tests,
                COUNT(DISTINCT CASE WHEN t.status='Passed' THEN t.id END) AS passed_tests,
                COUNT(DISTINCT CASE WHEN t.status NOT IN ('Passed', 'Failed') THEN t.id END) AS pending_tests,
                COUNT(DISTINCT CASE WHEN nc.status!='Closed' THEN nc.id END) AS open_ncs
                FROM projects p LEFT JOIN tests t ON t.project_id=p.id
                LEFT JOIN non_conformities nc ON nc.project_id=p.id {clauses}
                GROUP BY p.id ORDER BY p.name"""
        elif report_name == "Detailed PIV tracking":
            query = f"""SELECT p.project_code, p.name AS project, t.test_code, t.description,
                c.name AS component, s.name AS supplier, t.category, t.planned_start,
                t.planned_end, t.actual_test_date, t.status, t.result, t.report_reference
                FROM tests t JOIN projects p ON p.id=t.project_id
                LEFT JOIN components c ON c.id=t.component_id
                LEFT JOIN suppliers s ON s.id=t.supplier_id {clauses.replace('p.archived=0', 'p.archived=0')}
                ORDER BY p.name, t.planned_start"""
        elif report_name == "Test status and results":
            query = f"""SELECT p.project_code, p.name AS project, t.test_code, t.description,
                t.category, t.status, t.result, t.actual_test_date, t.report_reference,
                t.justified_disposition FROM tests t JOIN projects p ON p.id=t.project_id
                {clauses} ORDER BY p.name, t.status, t.test_code"""
        elif report_name == "Supplier delivery and conformity":
            query = f"""SELECT p.project_code, p.name AS project, s.name AS supplier,
                c.name AS component, sm.description AS sample, sm.required_quantity,
                sm.received_quantity, sm.required_date, sm.committed_date,
                sm.actual_receipt_date, sm.conformity FROM samples sm
                JOIN projects p ON p.id=sm.project_id
                LEFT JOIN suppliers s ON s.id=sm.supplier_id
                LEFT JOIN components c ON c.id=sm.component_id {clauses}
                ORDER BY p.name, sm.required_date"""
        elif report_name == "Open non-conformities":
            query = f"""SELECT p.project_code, p.name AS project, nc.nc_code, nc.detected_date,
                nc.severity, nc.status, nc.description, nc.containment, s.name AS supplier
                FROM non_conformities nc JOIN projects p ON p.id=nc.project_id
                LEFT JOIN suppliers s ON s.id=nc.supplier_id
                {clauses} AND nc.status!='Closed' ORDER BY nc.severity, nc.detected_date"""
        elif report_name == "Overdue actions":
            query = f"""SELECT p.project_code, p.name AS project, a.action_code, a.description,
                a.owner, a.due_date, a.priority, a.status, s.name AS supplier
                FROM actions a JOIN projects p ON p.id=a.project_id
                LEFT JOIN suppliers s ON s.id=a.supplier_id
                {clauses} AND a.status NOT IN ('Closed', 'Cancelled') AND a.due_date<?
                ORDER BY a.due_date"""
            parameters = (*parameters, date.today().isoformat())
        else:
            project_rows = connection.execute(
                f"SELECT p.id, p.project_code, p.name FROM projects p {clauses} ORDER BY p.name",
                parameters,
            ).fetchall()
            records = []
            for project in project_rows:
                readiness = get_readiness(database_path, project["id"])
                records.append({
                    "project_code": project["project_code"],
                    "project": project["name"],
                    "ready": readiness["ready"],
                    "pending_criteria": "; ".join(readiness["pending"]),
                })
            return pd.DataFrame.from_records(records)
        return pd.read_sql_query(query, connection, params=parameters)


def export_csv(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8-sig")


def export_excel(frame: pd.DataFrame, sheet_name: str = "Report") -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    return output.getvalue()