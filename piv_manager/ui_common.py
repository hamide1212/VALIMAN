"""Shared helpers for Streamlit pages."""

from __future__ import annotations

from pathlib import Path
import sqlite3

import pandas as pd
import streamlit as st

from piv_manager.db import transaction


def rows(database_path: str | Path, query: str, parameters: tuple = ()):
    with transaction(database_path) as connection:
        return connection.execute(query, parameters).fetchall()


def show_rows(data, empty_message: str = "No records yet.") -> None:
    if not data:
        st.info(empty_message)
        return
    st.dataframe(pd.DataFrame([dict(row) for row in data]), width="stretch", hide_index=True)


def choice_options(data, label_key: str = "name") -> tuple[list[str], dict[str, int]]:
    labels = [f"{row[label_key]} · #{row['id']}" for row in data]
    return labels, {label: int(row["id"]) for label, row in zip(labels, data)}


def report_error(error: Exception) -> None:
    if isinstance(error, (ValueError, PermissionError, sqlite3.IntegrityError, FileExistsError)):
        st.error(str(error))
    else:
        st.error(f"The operation could not be completed: {error}")


def date_value(value):
    return value.isoformat() if value else None


def require_editor(can_edit: bool) -> bool:
    if not can_edit:
        st.info("Your account has read-only access.")
        return False
    return True
