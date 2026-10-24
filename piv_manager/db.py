"""SQLite connection management and versioned schema initialization."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 5

_INITIAL_SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'approver', 'editor', 'viewer')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE suppliers (
    id INTEGER PRIMARY KEY,
    supplier_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    site TEXT,
    address TEXT,
    email TEXT,
    phone TEXT,
    notes TEXT,
    archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE supplier_contacts (
    id INTEGER PRIMARY KEY,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    role TEXT,
    email TEXT,
    phone TEXT,
    is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0, 1))
);

CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    project_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    vehicle_program TEXT,
    project_manager TEXT,
    validation_pilot TEXT,
    start_date TEXT,
    target_validation_date TEXT,
    actual_completion_date TEXT,
    phase TEXT NOT NULL DEFAULT 'Concept' CHECK (phase IN ('Concept', 'Design', 'Validation', 'Production', 'Closed')),
    status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'On Hold', 'Completed', 'Archived')),
    archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1)),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE components (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    part_number TEXT NOT NULL,
    part_revision TEXT NOT NULL,
    description TEXT,
    UNIQUE(project_id, part_number, part_revision)
);

CREATE TABLE project_milestones (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'APQP',
    planned_date TEXT NOT NULL,
    actual_date TEXT,
    owner TEXT,
    status TEXT NOT NULL DEFAULT 'Planned' CHECK (status IN ('Planned', 'In Progress', 'Complete', 'Blocked')),
    mandatory INTEGER NOT NULL DEFAULT 1 CHECK (mandatory IN (0, 1)),
    notes TEXT
);

CREATE TABLE tests (
    id INTEGER PRIMARY KEY,
    test_code TEXT NOT NULL UNIQUE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    component_id INTEGER REFERENCES components(id) ON DELETE SET NULL,
    supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
    original_test_id INTEGER REFERENCES tests(id) ON DELETE SET NULL,
    description TEXT NOT NULL,
    validation_requirement TEXT,
    category TEXT NOT NULL CHECK (category IN ('Component test', 'Bench test', 'Laboratory test', 'Environmental test', 'Durability test', 'Vehicle test')),
    location TEXT,
    test_owner TEXT,
    laboratory TEXT,
    planned_start TEXT,
    planned_end TEXT,
    actual_test_date TEXT,
    sample_quantity INTEGER NOT NULL DEFAULT 1 CHECK (sample_quantity >= 0),
    sample_available INTEGER NOT NULL DEFAULT 0 CHECK (sample_available IN (0, 1)),
    required_documents TEXT,
    acceptance_criteria TEXT,
    result TEXT,
    report_reference TEXT,
    comments TEXT,
    status TEXT NOT NULL DEFAULT 'Not Planned' CHECK (status IN ('Not Planned', 'Planned', 'Ready', 'In Progress', 'Passed', 'Failed', 'Blocked', 'Retest Required')),
    mandatory INTEGER NOT NULL DEFAULT 1 CHECK (mandatory IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE test_history (
    id INTEGER PRIMARY KEY,
    test_id INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by TEXT,
    previous_status TEXT,
    new_status TEXT NOT NULL,
    result TEXT,
    notes TEXT
);

CREATE TABLE samples (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    component_id INTEGER REFERENCES components(id) ON DELETE SET NULL,
    supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
    description TEXT NOT NULL,
    required_quantity INTEGER NOT NULL DEFAULT 0 CHECK (required_quantity >= 0),
    committed_date TEXT,
    required_date TEXT,
    actual_receipt_date TEXT,
    received_quantity INTEGER NOT NULL DEFAULT 0 CHECK (received_quantity >= 0),
    conformity TEXT NOT NULL DEFAULT 'Unknown' CHECK (conformity IN ('Unknown', 'Conforming', 'Non-conforming', 'Missing')),
    notes TEXT
);

CREATE TABLE non_conformities (
    id INTEGER PRIMARY KEY,
    nc_code TEXT NOT NULL UNIQUE,
    test_id INTEGER REFERENCES tests(id) ON DELETE SET NULL,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    component_id INTEGER REFERENCES components(id) ON DELETE SET NULL,
    supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
    description TEXT NOT NULL,
    detected_date TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'Major' CHECK (severity IN ('Critical', 'Major', 'Minor')),
    containment TEXT,
    five_why TEXT,
    ishikawa TEXT,
    immediate_correction TEXT,
    effectiveness_verification TEXT,
    effectiveness_verified INTEGER NOT NULL DEFAULT 0 CHECK (effectiveness_verified IN (0, 1)),
    closure_approved_by TEXT,
    status TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ('Open', 'Containment', 'Root Cause Analysis', 'Action in Progress', 'Verification', 'Closed')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE actions (
    id INTEGER PRIMARY KEY,
    action_code TEXT NOT NULL UNIQUE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
    nc_id INTEGER REFERENCES non_conformities(id) ON DELETE CASCADE,
    test_id INTEGER REFERENCES tests(id) ON DELETE SET NULL,
    source_type TEXT NOT NULL DEFAULT 'Project review',
    description TEXT NOT NULL,
    owner TEXT NOT NULL,
    creation_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'Medium' CHECK (priority IN ('Low', 'Medium', 'High', 'Critical')),
    status TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ('Open', 'In Progress', 'Blocked', 'Closed', 'Cancelled')),
    evidence TEXT,
    closure_date TEXT,
    mandatory INTEGER NOT NULL DEFAULT 0 CHECK (mandatory IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE supplier_visits (
    id INTEGER PRIMARY KEY,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    visit_date TEXT NOT NULL,
    visitors TEXT,
    purpose TEXT NOT NULL,
    findings TEXT,
    notes TEXT
);

CREATE TABLE checklist_items (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    component_id INTEGER REFERENCES components(id) ON DELETE CASCADE,
    criterion TEXT NOT NULL,
    category TEXT NOT NULL,
    satisfied INTEGER NOT NULL DEFAULT 0 CHECK (satisfied IN (0, 1)),
    evidence TEXT,
    mandatory INTEGER NOT NULL DEFAULT 1 CHECK (mandatory IN (0, 1)),
    checked_by TEXT,
    checked_at TEXT,
    UNIQUE(project_id, component_id, criterion)
);

CREATE TABLE final_approval_history (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    component_id INTEGER REFERENCES components(id) ON DELETE SET NULL,
    decision TEXT NOT NULL CHECK (decision IN ('Not Ready', 'Ready for Review', 'Approved', 'Rejected', 'On Hold')),
    approver TEXT NOT NULL,
    decision_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    comments TEXT,
    readiness_snapshot TEXT NOT NULL
);

CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    document_code TEXT NOT NULL UNIQUE,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    component_id INTEGER REFERENCES components(id) ON DELETE SET NULL,
    test_id INTEGER REFERENCES tests(id) ON DELETE SET NULL,
    supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
    nc_id INTEGER REFERENCES non_conformities(id) ON DELETE SET NULL,
    action_id INTEGER REFERENCES actions(id) ON DELETE SET NULL,
    original_name TEXT NOT NULL,
    stored_name TEXT NOT NULL UNIQUE,
    relative_path TEXT NOT NULL,
    mime_type TEXT,
    file_size INTEGER NOT NULL CHECK (file_size >= 0),
    category TEXT NOT NULL,
    uploaded_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE audit_events (
    id INTEGER PRIMARY KEY,
    occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    username TEXT,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    operation TEXT NOT NULL,
    details TEXT
);

CREATE INDEX idx_projects_status ON projects(status, archived);
CREATE INDEX idx_components_project ON components(project_id);
CREATE INDEX idx_milestones_project_date ON project_milestones(project_id, planned_date);
CREATE INDEX idx_tests_project_status ON tests(project_id, status);
CREATE INDEX idx_tests_due ON tests(planned_end);
CREATE INDEX idx_samples_supplier ON samples(supplier_id, required_date);
CREATE INDEX idx_nc_project_status ON non_conformities(project_id, status);
CREATE INDEX idx_actions_due_status ON actions(due_date, status);
CREATE INDEX idx_actions_owner ON actions(owner, status);
CREATE INDEX idx_documents_project ON documents(project_id);
CREATE INDEX idx_audit_occurred ON audit_events(occurred_at);
"""

_MIGRATIONS = {
    2: "ALTER TABLE tests ADD COLUMN justified_disposition TEXT;",
    3: """
        ALTER TABLE tests ADD COLUMN original_planned_start TEXT;
        ALTER TABLE tests ADD COLUMN original_planned_end TEXT;
        ALTER TABLE project_milestones ADD COLUMN original_planned_date TEXT;
        UPDATE tests SET original_planned_start=planned_start, original_planned_end=planned_end;
        UPDATE project_milestones SET original_planned_date=planned_date;
        CREATE TABLE schedule_history (
            id INTEGER PRIMARY KEY,
            entity_type TEXT NOT NULL CHECK (entity_type IN ('test', 'milestone')),
            entity_id INTEGER NOT NULL,
            changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            changed_by TEXT,
            previous_start TEXT,
            previous_end TEXT,
            new_start TEXT,
            new_end TEXT,
            reason TEXT
        );
        CREATE INDEX idx_schedule_history_entity ON schedule_history(entity_type, entity_id, changed_at);
    """,
    4: """
        ALTER TABLE actions ADD COLUMN effectiveness_verification TEXT;
        ALTER TABLE actions ADD COLUMN effectiveness_verified INTEGER NOT NULL DEFAULT 0
            CHECK (effectiveness_verified IN (0, 1));
    """,
    5: """
        ALTER TABLE final_approval_history ADD COLUMN approver_user_id INTEGER
            REFERENCES users(id) ON DELETE SET NULL;
        CREATE TRIGGER audit_final_approval AFTER INSERT ON final_approval_history
        BEGIN
            INSERT INTO audit_events(username, entity_type, entity_id, operation, details)
            VALUES (
                (SELECT username FROM users WHERE id=NEW.approver_user_id),
                'final_validation', CAST(NEW.project_id AS TEXT), lower(NEW.decision), NEW.comments
            );
        END;
    """,
}


def connect(database_path: str | Path) -> sqlite3.Connection:
    """Open a configured SQLite connection with foreign keys enabled."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 15000")
    return connection


@contextmanager
def transaction(database_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Provide an atomic transaction and always close its connection."""
    connection = connect(database_path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database(database_path: str | Path) -> None:
    """Apply any schema migrations without discarding existing records."""
    connection = connect(database_path)
    try:
        current_version = connection.execute("PRAGMA user_version").fetchone()[0]
        if current_version > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema {current_version} is newer than supported schema {SCHEMA_VERSION}."
            )
        if current_version == 0:
            try:
                connection.executescript(
                    f"BEGIN IMMEDIATE;\n{_INITIAL_SCHEMA}\n"
                    "PRAGMA user_version = 1;\nCOMMIT;"
                )
            except Exception:
                if connection.in_transaction:
                    connection.rollback()
                raise
            current_version = 1
        while current_version < SCHEMA_VERSION:
            next_version = current_version + 1
            migration = _MIGRATIONS.get(next_version)
            if migration is None:
                raise RuntimeError(f"Missing database migration {next_version}.")
            try:
                connection.executescript(
                    f"BEGIN IMMEDIATE;\n{migration}\n"
                    f"PRAGMA user_version = {next_version};\nCOMMIT;"
                )
            except Exception:
                if connection.in_transaction:
                    connection.rollback()
                raise
            current_version = next_version
    finally:
        connection.close()
