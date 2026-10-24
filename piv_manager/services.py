"""Validated business operations for VALIMAN records."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import json
import shutil
import sqlite3
import uuid

from piv_manager.db import transaction


def _code(prefix: str) -> str:
    return f"{prefix}-{date.today():%y%m%d}-{uuid.uuid4().hex[:6].upper()}"


def _validate_date(value: str | None, label: str, required: bool = False) -> None:
    if required and not value:
        raise ValueError(f"{label} is required.")
    if value:
        try:
            date.fromisoformat(value)
        except ValueError as error:
            raise ValueError(f"{label} must use YYYY-MM-DD format.") from error


def _audit(connection: sqlite3.Connection, entity: str, entity_id: int | str,
           operation: str, username: str, details: str = "") -> None:
    connection.execute(
        "INSERT INTO audit_events(username, entity_type, entity_id, operation, details) "
        "VALUES (?, ?, ?, ?, ?)",
        (username, entity, str(entity_id), operation, details),
    )


def list_projects(database_path: str | Path, include_archived: bool = False):
    with transaction(database_path) as connection:
        condition = "" if include_archived else "WHERE p.archived = 0"
        return connection.execute(
            f"""SELECT p.*, COUNT(DISTINCT t.id) AS test_count,
                       COUNT(DISTINCT c.id) AS component_count
                FROM projects p LEFT JOIN tests t ON t.project_id = p.id
                LEFT JOIN components c ON c.project_id = p.id
                {condition} GROUP BY p.id ORDER BY p.updated_at DESC"""
        ).fetchall()


def create_project(database_path: str | Path, *, name: str, vehicle_program: str = "",
                   project_manager: str = "", validation_pilot: str = "",
                   start_date: str | None = None, target_validation_date: str | None = None,
                   phase: str = "Concept", username: str = "local") -> int:
    if not name.strip():
        raise ValueError("Project name is required.")
    _validate_date(start_date, "Project start date")
    _validate_date(target_validation_date, "Target validation date")
    with transaction(database_path) as connection:
        cursor = connection.execute(
            """INSERT INTO projects(project_code, name, vehicle_program, project_manager,
               validation_pilot, start_date, target_validation_date, phase)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (_code("PIV"), name.strip(), vehicle_program.strip(), project_manager.strip(),
             validation_pilot.strip(), start_date or None, target_validation_date or None, phase),
        )
        project_id = cursor.lastrowid
        _audit(connection, "project", project_id, "create", username, name.strip())
        return project_id


def update_project(database_path: str | Path, project_id: int, *, name: str,
                   vehicle_program: str = "", project_manager: str = "",
                   validation_pilot: str = "", start_date: str | None = None,
                   target_validation_date: str | None = None, phase: str = "Concept",
                   status: str = "Active", actual_completion_date: str | None = None,
                   username: str = "local") -> None:
    if not name.strip():
        raise ValueError("Project name is required.")
    _validate_date(start_date, "Project start date")
    _validate_date(target_validation_date, "Target validation date")
    _validate_date(actual_completion_date, "Actual completion date")
    with transaction(database_path) as connection:
        cursor = connection.execute(
            """UPDATE projects SET name=?, vehicle_program=?, project_manager=?,
               validation_pilot=?, start_date=?, target_validation_date=?, phase=?, status=?,
               actual_completion_date=?,
               updated_at=CURRENT_TIMESTAMP WHERE id=? AND archived=0""",
            (name.strip(), vehicle_program.strip(), project_manager.strip(), validation_pilot.strip(),
             start_date or None, target_validation_date or None, phase, status,
             actual_completion_date or None, project_id),
        )
        if not cursor.rowcount:
            raise ValueError("Project was not found or is archived.")
        _audit(connection, "project", project_id, "update", username, name.strip())


def archive_project(database_path: str | Path, project_id: int, username: str = "local") -> None:
    with transaction(database_path) as connection:
        cursor = connection.execute(
            "UPDATE projects SET archived=1, status='Archived', updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (project_id,),
        )
        if not cursor.rowcount:
            raise ValueError("Project not found.")
        _audit(connection, "project", project_id, "archive", username)


def list_suppliers(database_path: str | Path):
    with transaction(database_path) as connection:
        return connection.execute(
            "SELECT * FROM suppliers WHERE archived=0 ORDER BY name COLLATE NOCASE"
        ).fetchall()


def create_supplier(database_path: str | Path, *, name: str, site: str = "",
                    email: str = "", phone: str = "", username: str = "local") -> int:
    if not name.strip():
        raise ValueError("Supplier name is required.")
    with transaction(database_path) as connection:
        cursor = connection.execute(
            "INSERT INTO suppliers(supplier_code, name, site, email, phone) VALUES (?, ?, ?, ?, ?)",
            (_code("SUP"), name.strip(), site.strip(), email.strip(), phone.strip()),
        )
        supplier_id = cursor.lastrowid
        _audit(connection, "supplier", supplier_id, "create", username, name.strip())
        return supplier_id


def update_supplier(database_path: str | Path, supplier_id: int, *, name: str,
                    site: str = "", email: str = "", phone: str = "",
                    username: str = "local") -> None:
    if not name.strip():
        raise ValueError("Supplier name is required.")
    with transaction(database_path) as connection:
        cursor = connection.execute(
            """UPDATE suppliers SET name=?, site=?, email=?, phone=?,
               updated_at=CURRENT_TIMESTAMP WHERE id=? AND archived=0""",
            (name.strip(), site.strip(), email.strip(), phone.strip(), supplier_id),
        )
        if not cursor.rowcount:
            raise ValueError("Supplier was not found or is archived.")
        _audit(connection, "supplier", supplier_id, "update", username, name.strip())


def create_supplier_contact(database_path: str | Path, *, supplier_id: int, name: str,
                            role: str = "", email: str = "", phone: str = "",
                            is_primary: bool = False, username: str = "local") -> int:
    if not name.strip():
        raise ValueError("Contact name is required.")
    with transaction(database_path) as connection:
        if is_primary:
            connection.execute(
                "UPDATE supplier_contacts SET is_primary=0 WHERE supplier_id=?", (supplier_id,)
            )
        cursor = connection.execute(
            """INSERT INTO supplier_contacts(supplier_id, name, role, email, phone, is_primary)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (supplier_id, name.strip(), role.strip(), email.strip(), phone.strip(), int(is_primary)),
        )
        _audit(connection, "supplier_contact", cursor.lastrowid, "create", username, name.strip())
        return cursor.lastrowid


def create_component(database_path: str | Path, *, project_id: int, name: str,
                     part_number: str, part_revision: str, supplier_id: int | None = None) -> int:
    if not all(value.strip() for value in (name, part_number, part_revision)):
        raise ValueError("Component name, part number, and revision are required.")
    with transaction(database_path) as connection:
        cursor = connection.execute(
            """INSERT INTO components(project_id, supplier_id, name, part_number, part_revision)
               VALUES (?, ?, ?, ?, ?)""",
            (project_id, supplier_id or None, name.strip(), part_number.strip(), part_revision.strip()),
        )
        _audit(connection, "component", cursor.lastrowid, "create", "local", part_number.strip())
        return cursor.lastrowid


def create_test(database_path: str | Path, *, project_id: int, description: str,
                category: str, component_id: int | None = None, supplier_id: int | None = None,
                original_test_id: int | None = None,
                validation_requirement: str = "", test_owner: str = "",
                location: str = "", laboratory: str = "", required_documents: str = "",
                sample_available: bool = False,
                planned_start: str | None = None, planned_end: str | None = None,
                sample_quantity: int = 1, status: str = "Not Planned",
                acceptance_criteria: str = "", mandatory: bool = True,
                username: str = "local") -> int:
    if not description.strip():
        raise ValueError("Test description is required.")
    _validate_date(planned_start, "Planned start date")
    _validate_date(planned_end, "Planned end date")
    if planned_start and planned_end and planned_end < planned_start:
        raise ValueError("Planned end date cannot be before planned start date.")
    if sample_quantity < 0:
        raise ValueError("Sample quantity cannot be negative.")
    if status == "Failed":
        raise ValueError("Create the test first, then record a linked non-conformity or justified disposition.")
    with transaction(database_path) as connection:
        if original_test_id:
            original = connection.execute(
                "SELECT project_id FROM tests WHERE id=?", (original_test_id,)
            ).fetchone()
            if original is None or original["project_id"] != project_id:
                raise ValueError("A retest must link to an existing test in the same project.")
        cursor = connection.execute(
                """INSERT INTO tests(test_code, project_id, component_id, supplier_id, original_test_id,
                    description, validation_requirement, category, location, test_owner, laboratory,
                    planned_start, planned_end, sample_quantity, sample_available, required_documents,
                    acceptance_criteria, status, mandatory)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (_code("TEST"), project_id, component_id or None, supplier_id or None,
                 original_test_id or None, description.strip(), validation_requirement.strip(), category,
                 location.strip(), test_owner.strip(), laboratory.strip(), planned_start or None,
                 planned_end or None, sample_quantity, int(sample_available), required_documents.strip(),
                 acceptance_criteria.strip(), status, int(mandatory)),
        )
        test_id = cursor.lastrowid
        if original_test_id:
            original = connection.execute(
                "SELECT status FROM tests WHERE id=?", (original_test_id,)
            ).fetchone()
            connection.execute(
                "UPDATE tests SET status='Retest Required', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (original_test_id,),
            )
            connection.execute(
                """INSERT INTO test_history(test_id, changed_by, previous_status, new_status, notes)
                   VALUES (?, ?, ?, 'Retest Required', ?)""",
                (original_test_id, username, original["status"], f"Retest {test_id} created"),
            )
        connection.execute(
            "INSERT INTO test_history(test_id, changed_by, new_status, notes) VALUES (?, ?, ?, ?)",
            (test_id, username, status, "Test created"),
        )
        _audit(connection, "test", test_id, "create", username, description.strip())
        return test_id


def update_test_status(database_path: str | Path, test_id: int, *, status: str,
                       result: str = "", justified_disposition: str = "",
                       actual_test_date: str | None = None, report_reference: str = "",
                       comments: str = "", sample_available: bool | None = None,
                       username: str = "local") -> None:
    _validate_date(actual_test_date, "Actual test date")
    with transaction(database_path) as connection:
        test = connection.execute("SELECT * FROM tests WHERE id=?", (test_id,)).fetchone()
        if test is None:
            raise ValueError("Test not found.")
        if status == "Failed":
            linked_nc = connection.execute(
                "SELECT 1 FROM non_conformities WHERE test_id=? LIMIT 1", (test_id,)
            ).fetchone()
            if not linked_nc and not justified_disposition.strip():
                raise ValueError("A failed test requires a linked non-conformity or documented disposition.")
        connection.execute(
            """UPDATE tests SET status=?, result=?, justified_disposition=?, actual_test_date=?,
                    report_reference=?, comments=?, sample_available=COALESCE(?, sample_available),
                    updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (status, result.strip(), justified_disposition.strip(), actual_test_date or None,
                 report_reference.strip(), comments.strip(),
                 int(sample_available) if sample_available is not None else None, test_id),
        )
        connection.execute(
            """INSERT INTO test_history(test_id, changed_by, previous_status, new_status, result, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (test_id, username, test["status"], status, result.strip(), comments.strip()),
        )
        _audit(connection, "test", test_id, "status_change", username, f"{test['status']} -> {status}")


def reschedule_test(database_path: str | Path, test_id: int, *, planned_start: str | None,
                    planned_end: str | None, reason: str, username: str = "local") -> None:
    _validate_date(planned_start, "Planned start date")
    _validate_date(planned_end, "Planned end date")
    if planned_start and planned_end and planned_end < planned_start:
        raise ValueError("Planned end date cannot be before planned start date.")
    with transaction(database_path) as connection:
        test = connection.execute("SELECT * FROM tests WHERE id=?", (test_id,)).fetchone()
        if test is None:
            raise ValueError("Test not found.")
        connection.execute(
            """UPDATE tests SET original_planned_start=COALESCE(original_planned_start, planned_start),
               original_planned_end=COALESCE(original_planned_end, planned_end), planned_start=?,
               planned_end=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (planned_start or None, planned_end or None, test_id),
        )
        connection.execute(
            """INSERT INTO schedule_history(entity_type, entity_id, changed_by, previous_start,
               previous_end, new_start, new_end, reason) VALUES ('test', ?, ?, ?, ?, ?, ?, ?)""",
            (test_id, username, test["planned_start"], test["planned_end"],
             planned_start or None, planned_end or None, reason.strip()),
        )
        _audit(connection, "test", test_id, "reschedule", username, reason.strip())


def create_action(database_path: str | Path, *, project_id: int, description: str,
                  owner: str, due_date: str, priority: str = "Medium",
                  supplier_id: int | None = None, nc_id: int | None = None,
                  test_id: int | None = None, source_type: str = "Project review",
                  mandatory: bool = False, username: str = "local") -> int:
    if not description.strip() or not owner.strip():
        raise ValueError("Action description and owner are required.")
    _validate_date(due_date, "Action due date", required=True)
    with transaction(database_path) as connection:
        cursor = connection.execute(
            """INSERT INTO actions(action_code, project_id, supplier_id, nc_id, test_id,
               source_type, description, owner, creation_date, due_date, priority, mandatory)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (_code("ACT"), project_id, supplier_id or None, nc_id or None, test_id or None,
             source_type, description.strip(), owner.strip(), date.today().isoformat(), due_date,
             priority, int(mandatory)),
        )
        action_id = cursor.lastrowid
        _audit(connection, "action", action_id, "create", username, description.strip())
        return action_id


def update_action(database_path: str | Path, action_id: int, *, status: str,
                  evidence: str = "", effectiveness_verification: str = "",
                  effectiveness_verified: bool = False, username: str = "local") -> None:
    if status == "Closed" and not evidence.strip():
        raise ValueError("Closure evidence is required before closing an action.")
    with transaction(database_path) as connection:
        action = connection.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
        if action is None:
            raise ValueError("Action not found.")
        if status == "Closed" and action["mandatory"] and (
            not effectiveness_verified or not effectiveness_verification.strip()
        ):
            raise ValueError("Mandatory action effectiveness must be verified before closure.")
        closure_date = date.today().isoformat() if status == "Closed" else None
        connection.execute(
            """UPDATE actions SET status=?, evidence=?, closure_date=?,
               effectiveness_verification=?, effectiveness_verified=?,
               updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (status, evidence.strip(), closure_date, effectiveness_verification.strip(),
             int(effectiveness_verified), action_id),
        )
        _audit(connection, "action", action_id, "update", username, f"Status: {status}")


def create_non_conformity(database_path: str | Path, *, project_id: int,
                          description: str, detected_date: str,
                          test_id: int | None = None, component_id: int | None = None,
                          supplier_id: int | None = None, severity: str = "Major",
                          containment: str = "", username: str = "local") -> int:
    if not description.strip():
        raise ValueError("Non-conformity description is required.")
    _validate_date(detected_date, "Detection date", required=True)
    with transaction(database_path) as connection:
        originating_test = None
        if test_id:
            originating_test = connection.execute(
                "SELECT project_id, status FROM tests WHERE id=?", (test_id,)
            ).fetchone()
            if originating_test is None or originating_test["project_id"] != project_id:
                raise ValueError("Originating test must belong to the selected project.")
        nc_code = _code("NC")
        cursor = connection.execute(
            """INSERT INTO non_conformities(nc_code, test_id, project_id, component_id,
               supplier_id, description, detected_date, severity, containment, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (nc_code, test_id or None, project_id, component_id or None, supplier_id or None,
             description.strip(), detected_date, severity, containment.strip(),
             "Containment" if containment.strip() else "Open"),
        )
        nc_id = cursor.lastrowid
        if test_id:
            connection.execute(
                """UPDATE tests SET status='Failed', result='Failed', updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (test_id,),
            )
            connection.execute(
                """INSERT INTO test_history(test_id, changed_by, previous_status, new_status, notes)
                   VALUES (?, ?, ?, 'Failed', ?)""",
                (test_id, username, originating_test["status"], f"Linked non-conformity {nc_code}"),
            )
        _audit(connection, "non_conformity", nc_id, "create", username, description.strip())
        return nc_id


def update_non_conformity(database_path: str | Path, nc_id: int, *, status: str,
                          five_why: str = "", ishikawa: str = "",
                          immediate_correction: str = "", containment: str = "",
                          effectiveness_verification: str = "",
                          effectiveness_verified: bool = False,
                          closure_approved_by: str = "", username: str = "local") -> None:
    with transaction(database_path) as connection:
        nc = connection.execute("SELECT * FROM non_conformities WHERE id=?", (nc_id,)).fetchone()
        if nc is None:
            raise ValueError("Non-conformity not found.")
        if status == "Closed":
            open_actions = connection.execute(
                "SELECT COUNT(*) FROM actions WHERE nc_id=? AND status NOT IN ('Closed', 'Cancelled')",
                (nc_id,),
            ).fetchone()[0]
            if open_actions:
                raise ValueError("Close all linked corrective actions before closing this non-conformity.")
            if not effectiveness_verified or not effectiveness_verification.strip():
                raise ValueError("Record and verify effectiveness before closing this non-conformity.")
            if not closure_approved_by.strip():
                raise ValueError("Closure approval is required.")
        connection.execute(
            """UPDATE non_conformities SET status=?, five_why=?, ishikawa=?,
               immediate_correction=?, containment=?, effectiveness_verification=?,
               effectiveness_verified=?, closure_approved_by=?, updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (status, five_why.strip(), ishikawa.strip(), immediate_correction.strip(),
             containment.strip(), effectiveness_verification.strip(), int(effectiveness_verified),
             closure_approved_by.strip() if status == "Closed" else "", nc_id),
        )
        _audit(connection, "non_conformity", nc_id, "update", username, f"Status: {status}")


def create_milestone(database_path: str | Path, *, project_id: int, name: str,
                     planned_date: str, category: str = "APQP", owner: str = "",
                     mandatory: bool = True) -> int:
    if not name.strip():
        raise ValueError("Milestone name is required.")
    _validate_date(planned_date, "Milestone planned date", required=True)
    with transaction(database_path) as connection:
        cursor = connection.execute(
            """INSERT INTO project_milestones(project_id, name, category, planned_date,
               owner, mandatory) VALUES (?, ?, ?, ?, ?, ?)""",
            (project_id, name.strip(), category, planned_date, owner.strip(), int(mandatory)),
        )
        _audit(connection, "milestone", cursor.lastrowid, "create", "local", name.strip())
        return cursor.lastrowid


def create_sample(database_path: str | Path, *, project_id: int, description: str,
                  required_quantity: int, required_date: str | None = None,
                  supplier_id: int | None = None, component_id: int | None = None,
                  committed_date: str | None = None, received_quantity: int = 0,
                  actual_receipt_date: str | None = None, conformity: str = "Unknown",
                  notes: str = "", username: str = "local") -> int:
    if not description.strip():
        raise ValueError("Sample description is required.")
    for value, label in ((required_date, "Required date"), (committed_date, "Committed date"),
                         (actual_receipt_date, "Actual receipt date")):
        _validate_date(value, label)
    if required_quantity < 0 or received_quantity < 0:
        raise ValueError("Sample quantities cannot be negative.")
    with transaction(database_path) as connection:
        cursor = connection.execute(
            """INSERT INTO samples(project_id, component_id, supplier_id, description,
               required_quantity, committed_date, required_date, actual_receipt_date,
               received_quantity, conformity, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (project_id, component_id or None, supplier_id or None, description.strip(),
             required_quantity, committed_date or None, required_date or None,
             actual_receipt_date or None, received_quantity, conformity, notes.strip()),
        )
        _audit(connection, "sample", cursor.lastrowid, "create", username, description.strip())
        return cursor.lastrowid


def update_sample_delivery(database_path: str | Path, sample_id: int, *,
                           committed_date: str | None = None,
                           actual_receipt_date: str | None = None,
                           received_quantity: int, conformity: str,
                           notes: str = "", username: str = "local") -> None:
    _validate_date(committed_date, "Committed date")
    _validate_date(actual_receipt_date, "Actual receipt date")
    if received_quantity < 0:
        raise ValueError("Received quantity cannot be negative.")
    with transaction(database_path) as connection:
        cursor = connection.execute(
            """UPDATE samples SET committed_date=?, actual_receipt_date=?, received_quantity=?,
               conformity=?, notes=? WHERE id=?""",
            (committed_date or None, actual_receipt_date or None, received_quantity,
             conformity, notes.strip(), sample_id),
        )
        if not cursor.rowcount:
            raise ValueError("Sample delivery record not found.")
        _audit(connection, "sample", sample_id, "delivery_update", username, conformity)


def create_supplier_visit(database_path: str | Path, *, supplier_id: int,
                          visit_date: str, purpose: str, project_id: int | None = None,
                          visitors: str = "", findings: str = "", notes: str = "",
                          username: str = "local") -> int:
    _validate_date(visit_date, "Supplier visit date", required=True)
    if not purpose.strip():
        raise ValueError("Visit purpose is required.")
    with transaction(database_path) as connection:
        cursor = connection.execute(
            """INSERT INTO supplier_visits(supplier_id, project_id, visit_date, visitors,
               purpose, findings, notes) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (supplier_id, project_id or None, visit_date, visitors.strip(), purpose.strip(),
             findings.strip(), notes.strip()),
        )
        _audit(connection, "supplier_visit", cursor.lastrowid, "create", username, purpose.strip())
        return cursor.lastrowid


def update_milestone(database_path: str | Path, milestone_id: int, *, status: str,
                     actual_date: str | None = None, planned_date: str | None = None,
                     reason: str = "", username: str = "local") -> None:
    _validate_date(actual_date, "Milestone actual date")
    _validate_date(planned_date, "Milestone planned date")
    with transaction(database_path) as connection:
        milestone = connection.execute(
            "SELECT * FROM project_milestones WHERE id=?", (milestone_id,)
        ).fetchone()
        if milestone is None:
            raise ValueError("Milestone not found.")
        connection.execute(
            """UPDATE project_milestones SET status=?, actual_date=?,
               original_planned_date=COALESCE(original_planned_date, planned_date),
               planned_date=COALESCE(?, planned_date) WHERE id=?""",
            (status, actual_date or None, planned_date or None, milestone_id),
        )
        if planned_date and planned_date != milestone["planned_date"]:
            connection.execute(
                """INSERT INTO schedule_history(entity_type, entity_id, changed_by, previous_start,
                   previous_end, new_start, new_end, reason)
                   VALUES ('milestone', ?, ?, ?, ?, ?, ?, ?)""",
                (milestone_id, username, milestone["planned_date"], milestone["planned_date"],
                 planned_date, planned_date, reason.strip()),
            )
        _audit(connection, "milestone", milestone_id, "update", username, f"Status: {status}")


def get_dashboard_data(database_path: str | Path, *, project_id: int | None = None,
                       supplier_id: int | None = None, component_id: int | None = None,
                       start_date: str | None = None, end_date: str | None = None) -> dict:
    test_filters = []
    test_parameters: list[object] = []
    if project_id:
        test_filters.append("project_id=?")
        test_parameters.append(project_id)
    if supplier_id:
        test_filters.append("supplier_id=?")
        test_parameters.append(supplier_id)
    if component_id:
        test_filters.append("component_id=?")
        test_parameters.append(component_id)
    if start_date:
        test_filters.append("COALESCE(actual_test_date, planned_end) >= ?")
        test_parameters.append(start_date)
    if end_date:
        test_filters.append("COALESCE(actual_test_date, planned_end) <= ?")
        test_parameters.append(end_date)
    test_where = " AND ".join(test_filters) or "1=1"
    action_filters = []
    action_parameters: list[object] = []
    if project_id:
        action_filters.append("a.project_id=?")
        action_parameters.append(project_id)
    if supplier_id:
        action_filters.append("a.supplier_id=?")
        action_parameters.append(supplier_id)
    if start_date:
        action_filters.append("a.due_date >= ?")
        action_parameters.append(start_date)
    if end_date:
        action_filters.append("a.due_date <= ?")
        action_parameters.append(end_date)
    action_where = " AND ".join(action_filters) or "1=1"
    nc_filters = ["nc.status!='Closed'"]
    nc_parameters: list[object] = []
    if project_id:
        nc_filters.append("nc.project_id=?")
        nc_parameters.append(project_id)
    if supplier_id:
        nc_filters.append("nc.supplier_id=?")
        nc_parameters.append(supplier_id)
    if component_id:
        nc_filters.append("nc.component_id=?")
        nc_parameters.append(component_id)
    if start_date:
        nc_filters.append("nc.detected_date >= ?")
        nc_parameters.append(start_date)
    if end_date:
        nc_filters.append("nc.detected_date <= ?")
        nc_parameters.append(end_date)
    nc_where = " AND ".join(nc_filters)
    deadline_start = start_date or date.today().isoformat()
    deadline_end = end_date or date.fromordinal(date.today().toordinal() + 30).isoformat()
    upcoming_test_filters = ["t.status NOT IN ('Passed', 'Failed')", "t.planned_end BETWEEN ? AND ?"]
    upcoming_test_parameters: list[object] = [deadline_start, deadline_end]
    upcoming_action_filters = ["a.status NOT IN ('Closed', 'Cancelled')", "a.due_date BETWEEN ? AND ?"]
    upcoming_action_parameters: list[object] = [deadline_start, deadline_end]
    for column, value in (("project_id", project_id), ("supplier_id", supplier_id),
                          ("component_id", component_id)):
        if value:
            upcoming_test_filters.append(f"t.{column}=?")
            upcoming_test_parameters.append(value)
    if project_id:
        upcoming_action_filters.append("a.project_id=?")
        upcoming_action_parameters.append(project_id)
    if supplier_id:
        upcoming_action_filters.append("a.supplier_id=?")
        upcoming_action_parameters.append(supplier_id)
    upcoming_test_where = " AND ".join(upcoming_test_filters)
    upcoming_action_where = " AND ".join(upcoming_action_filters)
    with transaction(database_path) as connection:
        projects = connection.execute(
            "SELECT COUNT(*) FROM projects WHERE archived=0 AND status='Active'"
            + (" AND id=?" if project_id else ""),
            (project_id,) if project_id else (),
        ).fetchone()[0]
        tests = connection.execute(
            f"SELECT status, COUNT(*) AS count FROM tests WHERE {test_where} GROUP BY status",
            test_parameters,
        ).fetchall()
        test_counts = {row["status"]: row["count"] for row in tests}
        open_ncs = connection.execute(
            f"SELECT COUNT(*) FROM non_conformities nc WHERE {nc_where}", nc_parameters,
        ).fetchone()[0]
        today = date.today().isoformat()
        overdue_actions = connection.execute(
            f"SELECT COUNT(*) FROM actions a WHERE a.status NOT IN ('Closed', 'Cancelled') "
            f"AND a.due_date < ? AND {action_where}", [today, *action_parameters],
        ).fetchone()[0]
        upcoming = connection.execute(
            f"""SELECT 'Test' AS kind, t.test_code AS code, t.description AS title,
                      t.planned_end AS due_date, t.status, p.name AS project
               FROM tests t JOIN projects p ON p.id=t.project_id
               WHERE {upcoming_test_where}
               UNION ALL
               SELECT 'Action', a.action_code, a.description, a.due_date, a.status, p.name
               FROM actions a JOIN projects p ON p.id=a.project_id
               WHERE {upcoming_action_where}
               ORDER BY due_date LIMIT 30""",
            (*upcoming_test_parameters, *upcoming_action_parameters),
        ).fetchall()
        critical_filters = [*nc_filters, "nc.severity IN ('Critical', 'Major')"]
        critical = connection.execute(
            f"""SELECT nc.nc_code, nc.description, nc.severity, nc.status, p.name AS project
               FROM non_conformities nc JOIN projects p ON p.id=nc.project_id
               WHERE {' AND '.join(critical_filters)}
               ORDER BY CASE nc.severity WHEN 'Critical' THEN 0 ELSE 1 END, nc.detected_date
               LIMIT 20"""
            , nc_parameters,
        ).fetchall()
        return {
            "active_projects": projects,
            "completed_tests": test_counts.get("Passed", 0),
            "pending_tests": sum(count for status, count in test_counts.items()
                                  if status not in {"Passed", "Failed"}),
            "overdue_tests": connection.execute(
                f"SELECT COUNT(*) FROM tests WHERE status NOT IN ('Passed', 'Failed') "
                f"AND planned_end < ? AND {test_where}", [today, *test_parameters]
            ).fetchone()[0],
            "open_non_conformities": open_ncs,
            "overdue_actions": overdue_actions,
            "test_status": tests,
            "upcoming": upcoming,
            "critical_issues": critical,
        }


def get_readiness(database_path: str | Path, project_id: int,
                  component_id: int | None = None) -> dict:
    conditions = ["project_id=?"]
    parameters: list[object] = [project_id]
    if component_id:
        conditions.append("component_id=?")
        parameters.append(component_id)
    scope = " AND ".join(conditions)
    with transaction(database_path) as connection:
        mandatory_tests = connection.execute(
            f"SELECT * FROM tests WHERE {scope} AND mandatory=1", parameters
        ).fetchall()
        critical_ncs = connection.execute(
            f"SELECT COUNT(*) FROM non_conformities WHERE {scope} "
            "AND severity='Critical' AND status!='Closed'", parameters
        ).fetchone()[0]
        action_scope = "project_id=? AND mandatory=1 AND status NOT IN ('Closed', 'Cancelled')"
        action_parameters: list[object] = [project_id]
        if component_id:
            action_scope += " AND (test_id IN (SELECT id FROM tests WHERE component_id=?) " \
                "OR nc_id IN (SELECT id FROM non_conformities WHERE component_id=?) " \
                "OR (test_id IS NULL AND nc_id IS NULL))"
            action_parameters.extend([component_id, component_id])
        mandatory_actions = connection.execute(
            f"SELECT COUNT(*) FROM actions WHERE {action_scope}", action_parameters
        ).fetchone()[0]
        if component_id:
            mandatory_actions += connection.execute(
                """SELECT COUNT(*) FROM actions WHERE project_id=? AND mandatory=1
                   AND status='Closed' AND effectiveness_verified=0
                   AND (test_id IN (SELECT id FROM tests WHERE component_id=?)
                     OR nc_id IN (SELECT id FROM non_conformities WHERE component_id=?))""",
                (project_id, component_id, component_id),
            ).fetchone()[0]
        else:
            mandatory_actions += connection.execute(
                """SELECT COUNT(*) FROM actions WHERE project_id=? AND mandatory=1
                   AND status='Closed' AND effectiveness_verified=0""", (project_id,)
            ).fetchone()[0]
        samples = connection.execute(
            f"SELECT * FROM samples WHERE {scope}", parameters
        ).fetchall()
        supplier_conformity = all(
            row["conformity"] == "Conforming" and row["received_quantity"] >= row["required_quantity"]
            for row in samples
        )
        checklist = connection.execute(
            f"SELECT * FROM checklist_items WHERE {scope} AND mandatory=1", parameters
        ).fetchall()
        checklist_status = {row["criterion"]: bool(row["satisfied"]) for row in checklist}
        tests_passed = bool(mandatory_tests) and all(
            row["status"] == "Passed" for row in mandatory_tests
        )
        samples_available = all(
            row["sample_available"] or row["sample_quantity"] == 0 for row in mandatory_tests
        )
        reports_referenced = bool(mandatory_tests) and all(
            row["status"] == "Passed" and bool(row["report_reference"])
            for row in mandatory_tests
        )
        required_documents_present = all(
            not row["required_documents"] or connection.execute(
                "SELECT 1 FROM documents WHERE test_id=? LIMIT 1", (row["id"],)
            ).fetchone()
            for row in mandatory_tests
        )
        criteria = {
            "Mandatory tests completed and passed": tests_passed,
            "Mandatory test reports received and approved": reports_referenced and required_documents_present and checklist_status.get(
                "Mandatory test reports received and approved", False
            ),
            "Required samples and documents available": samples_available and supplier_conformity and checklist_status.get(
                "Required samples and documents available", False
            ),
            "Supplier conformity confirmed": supplier_conformity and checklist_status.get(
                "Supplier conformity confirmed", False
            ),
            "Critical non-conformities closed": critical_ncs == 0,
            "Mandatory actions closed": mandatory_actions == 0,
            "Required reviews and approvals recorded": checklist_status.get(
                "Required reviews and approvals recorded", False
            ),
        }
        for item in checklist:
            criteria[item["criterion"]] = criteria.get(item["criterion"], True) and bool(item["satisfied"])
        pending = [criterion for criterion, satisfied in criteria.items() if not satisfied]
        return {"ready": not pending, "criteria": criteria, "pending": pending}


def set_checklist_item(database_path: str | Path, *, project_id: int,
                       criterion: str, category: str, satisfied: bool,
                       evidence: str = "", component_id: int | None = None,
                       checked_by: str = "local") -> None:
    if satisfied and not evidence.strip():
        raise ValueError("Add an evidence reference before marking this criterion satisfied.")
    with transaction(database_path) as connection:
        if component_id is None:
            existing = connection.execute(
                "SELECT id FROM checklist_items WHERE project_id=? AND component_id IS NULL AND criterion=?",
                (project_id, criterion),
            ).fetchone()
        else:
            existing = connection.execute(
                "SELECT id FROM checklist_items WHERE project_id=? AND component_id=? AND criterion=?",
                (project_id, component_id, criterion),
            ).fetchone()
        if existing:
            connection.execute(
                """UPDATE checklist_items SET category=?, satisfied=?, evidence=?, checked_by=?,
                   checked_at=CURRENT_TIMESTAMP WHERE id=?""",
                (category, int(satisfied), evidence.strip(), checked_by, existing["id"]),
            )
        else:
            connection.execute(
                """INSERT INTO checklist_items(project_id, component_id, criterion, category,
                   satisfied, evidence, checked_by, checked_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (project_id, component_id, criterion, category, int(satisfied), evidence.strip(), checked_by),
            )
        _audit(connection, "checklist", project_id, "update", checked_by, criterion)


def approve_validation(database_path: str | Path, *, project_id: int, approver: str,
                       approver_user_id: int, comments: str = "",
                       component_id: int | None = None, decision: str = "Approved") -> int:
    with transaction(database_path) as connection:
        authorized_user = connection.execute(
            "SELECT role, username FROM users WHERE id=? AND active=1", (approver_user_id,)
        ).fetchone()
    if authorized_user is None or authorized_user["role"] not in {"admin", "approver"}:
        raise PermissionError("Only an admin or authorized approver may record a decision.")
    readiness = get_readiness(database_path, project_id, component_id)
    if decision == "Approved" and not readiness["ready"]:
        raise ValueError("Final approval is blocked: " + "; ".join(readiness["pending"]))
    with transaction(database_path) as connection:
        cursor = connection.execute(
                """INSERT INTO final_approval_history(project_id, component_id, decision,
                    approver, comments, readiness_snapshot, approver_user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (project_id, component_id, decision, approver, comments.strip(),
                 json.dumps(readiness["criteria"], sort_keys=True), approver_user_id),
        )
        return cursor.lastrowid


def save_document(database_path: str | Path, *, content: bytes, original_name: str,
                  category: str, documents_dir: str | Path, mime_type: str = "",
                  project_id: int | None = None, component_id: int | None = None,
                  test_id: int | None = None, supplier_id: int | None = None,
                  nc_id: int | None = None, action_id: int | None = None,
                  uploaded_by: str = "local") -> int:
    from piv_manager.config import ALLOWED_DOCUMENT_EXTENSIONS, MAX_DOCUMENT_SIZE

    safe_name = Path(original_name).name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValueError("This document type is not allowed.")
    if not content or len(content) > MAX_DOCUMENT_SIZE:
        raise ValueError("Document must be non-empty and no larger than 25 MB.")
    directory = Path(documents_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    destination = directory / stored_name
    try:
        with destination.open("xb") as document_file:
            document_file.write(content)
        with transaction(database_path) as connection:
            cursor = connection.execute(
                """INSERT INTO documents(document_code, project_id, component_id, test_id,
                   supplier_id, nc_id, action_id, original_name, stored_name, relative_path,
                   mime_type, file_size, category, uploaded_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (_code("DOC"), project_id, component_id, test_id, supplier_id, nc_id, action_id,
                 safe_name, stored_name, stored_name, mime_type, len(content), category, uploaded_by),
            )
            _audit(connection, "document", cursor.lastrowid, "upload", uploaded_by, safe_name)
            return cursor.lastrowid
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def backup_database(database_path: str | Path, backup_path: str | Path) -> Path:
    source_path = Path(database_path)
    destination = Path(backup_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError("Backup destination already exists; choose a new filename.")
    source = sqlite3.connect(source_path)
    target = sqlite3.connect(destination)
    try:
        source.backup(target)
        result = target.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise sqlite3.DatabaseError(f"Backup integrity check failed: {result}")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        target.close()
        source.close()
    return destination


def restore_database(database_path: str | Path, backup_path: str | Path) -> None:
    target_path = Path(database_path)
    source_path = Path(backup_path)
    source = sqlite3.connect(source_path)
    target = sqlite3.connect(target_path)
    try:
        if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise sqlite3.DatabaseError("Selected backup failed its integrity check.")
        source.backup(target)
    finally:
        target.close()
        source.close()
    initialize_database(target_path)
