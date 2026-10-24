"""Local password authentication and account management."""

from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path

from piv_manager.db import transaction
from piv_manager.services import _audit

ITERATIONS = 310_000


def _password_hash(password: str, salt: bytes | None = None) -> str:
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters.")
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(actual.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def user_count(database_path: str | Path) -> int:
    with transaction(database_path) as connection:
        return connection.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0]


def create_user(database_path: str | Path, *, username: str, display_name: str,
                password: str, role: str, first_account: bool = False) -> int:
    normalized = username.strip().lower()
    if not normalized or not display_name.strip():
        raise ValueError("Username and display name are required.")
    if role not in {"admin", "approver", "editor", "viewer"}:
        raise ValueError("Choose a valid user role.")
    encoded = _password_hash(password)
    with transaction(database_path) as connection:
        active_count = connection.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0]
        if first_account and active_count:
            raise ValueError("Initial administrator setup has already been completed.")
        if not active_count and not first_account:
            raise ValueError("Create the initial administrator account first.")
        if first_account:
            role = "admin"
        cursor = connection.execute(
            "INSERT INTO users(username, password_hash, display_name, role) VALUES (?, ?, ?, ?)",
            (normalized, encoded, display_name.strip(), role),
        )
        _audit(connection, "user", cursor.lastrowid, "create", normalized, f"Role: {role}")
        return cursor.lastrowid


def authenticate(database_path: str | Path, username: str, password: str) -> dict | None:
    normalized = username.strip().lower()
    with transaction(database_path) as connection:
        user = connection.execute(
            "SELECT id, username, password_hash, display_name, role FROM users "
            "WHERE username=? AND active=1",
            (normalized,),
        ).fetchone()
        if user is None or not _verify_password(password, user["password_hash"]):
            return None
        _audit(connection, "user", user["id"], "login", user["username"])
        return {key: user[key] for key in ("id", "username", "display_name", "role")}


def get_active_user(database_path: str | Path, user_id: int) -> dict | None:
    with transaction(database_path) as connection:
        user = connection.execute(
            "SELECT id, username, display_name, role FROM users WHERE id=? AND active=1",
            (user_id,),
        ).fetchone()
        return dict(user) if user else None


def list_users(database_path: str | Path):
    with transaction(database_path) as connection:
        return connection.execute(
            "SELECT id, username, display_name, role, active, created_at FROM users ORDER BY username"
        ).fetchall()


def set_user_active(database_path: str | Path, user_id: int, active: bool,
                    actor: str) -> None:
    with transaction(database_path) as connection:
        if not active:
            admins = connection.execute(
                "SELECT COUNT(*) FROM users WHERE active=1 AND role='admin'"
            ).fetchone()[0]
            target = connection.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
            target_user = connection.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
            if target_user and target_user["username"] == actor.strip().lower():
                raise ValueError("You cannot deactivate your own account.")
            if target and target["role"] == "admin" and admins <= 1:
                raise ValueError("At least one active administrator must remain.")
        cursor = connection.execute("UPDATE users SET active=? WHERE id=?", (int(active), user_id))
        if not cursor.rowcount:
            raise ValueError("User not found.")
        _audit(connection, "user", user_id, "activate" if active else "deactivate", actor)
