"""Session authentication and project-role access control for Specra.

Passwords use the standard-library scrypt KDF. Session cookies contain opaque
random tokens; only SHA-256 token hashes are stored in SQLite.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from fastapi import Depends, HTTPException, Request, status

from app.core.storage.project_store import DEFAULT_DB_PATH
from app.core.database import persistent_storage_ready
from app.core.database import connect_database


AUTH_COOKIE_NAME = "specra_session"
SESSION_HOURS = 12
PASSWORD_SCRYPT_N = 2**14
PASSWORD_SCRYPT_R = 8
PASSWORD_SCRYPT_P = 1

PROJECT_ROLES = {
    "analyst",
    "planner",
    "architect",
    "tester",
    "reviewer",
    "developer",
    "viewer",
}
GLOBAL_ROLES = PROJECT_ROLES | {"admin"}

STAGE_ROLE = {
    "requirements": "analyst",
    "project_plan": "planner",
    "architecture": "architect",
    "technical_review": "reviewer",
    "review": "reviewer",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _now_text() -> str:
    return utc_now().isoformat()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=PASSWORD_SCRYPT_N,
        r=PASSWORD_SCRYPT_R,
        p=PASSWORD_SCRYPT_P,
        dklen=64,
    )


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters.")
    salt = secrets.token_bytes(16)
    digest = _password_hash(password, salt)
    return (
        "scrypt$" + str(PASSWORD_SCRYPT_N) + "$"
        + str(PASSWORD_SCRYPT_R) + "$" + str(PASSWORD_SCRYPT_P) + "$"
        + salt.hex() + "$" + digest.hex()
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_hex, digest_hex = encoded.split("$")
        if algorithm != "scrypt":
            return False
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(bytes.fromhex(digest_hex)),
        )
        return hmac.compare_digest(candidate, bytes.fromhex(digest_hex))
    except (ValueError, TypeError, MemoryError):
        return False


class AuthStore:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        connection = connect_database(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'viewer',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_sessions (
                    session_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS login_attempts (
                    identity_hash TEXT PRIMARY KEY,
                    failures INTEGER NOT NULL,
                    window_started_at TEXT NOT NULL,
                    locked_until TEXT
                );

                CREATE TABLE IF NOT EXISTS project_members (
                    project_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(project_id, user_id),
                    FOREIGN KEY(project_id) REFERENCES projects(project_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_user_sessions_user
                    ON user_sessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_project_members_user
                    ON project_members(user_id);
                """
            )

    def user_count(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    @staticmethod
    def public_user(row: sqlite3.Row | dict) -> dict:
        return {
            "user_id": row["user_id"],
            "email": row["email"],
            "display_name": row["display_name"],
            "role": row["role"],
            "is_active": bool(row["is_active"]),
            "created_at": row["created_at"],
        }

    def create_user(
        self,
        *,
        email: str,
        display_name: str,
        password: str,
        role: str = "viewer",
    ) -> dict:
        normalized_email = email.strip().casefold()
        normalized_name = display_name.strip()
        if not normalized_email or "@" not in normalized_email:
            raise ValueError("Enter a valid email address.")
        if not normalized_name:
            raise ValueError("Display name cannot be empty.")
        if role not in GLOBAL_ROLES:
            raise ValueError(f"Role must be one of: {', '.join(sorted(GLOBAL_ROLES))}.")

        encoded_password = hash_password(password)
        user_id = secrets.token_hex(16)
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO users (
                        user_id, email, display_name, password_hash,
                        role, is_active, created_at
                    ) VALUES (?, ?, ?, ?, ?, 1, ?)
                    """,
                    (
                        user_id,
                        normalized_email,
                        normalized_name,
                        encoded_password,
                        role,
                        _now_text(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("An account with this email already exists.") from exc

        return self.get_user_by_id(user_id)

    def get_user_by_email(self, email: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE email = ?",
                (email.strip().casefold(),),
            ).fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_users(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT user_id, email, display_name, role, is_active, created_at
                FROM users ORDER BY created_at ASC
                """
            ).fetchall()
            return [self.public_user(row) for row in rows]

    def set_user_active(self, user_id: str, is_active: bool) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE users SET is_active = ? WHERE user_id = ?",
                (1 if is_active else 0, user_id),
            )
            if is_active is False:
                connection.execute(
                    "DELETE FROM user_sessions WHERE user_id = ?",
                    (user_id,),
                )
            return cursor.rowcount > 0

    def update_user(
        self,
        user_id: str,
        *,
        role: str | None = None,
        is_active: bool | None = None,
    ) -> dict | None:
        if role is not None and role not in GLOBAL_ROLES:
            raise ValueError(
                f"Role must be one of: {', '.join(sorted(GLOBAL_ROLES))}."
            )
        updates: list[str] = []
        values: list[object] = []
        if role is not None:
            updates.append("role = ?")
            values.append(role)
        if is_active is not None:
            updates.append("is_active = ?")
            values.append(1 if is_active else 0)
        if not updates:
            return self.get_user_by_id(user_id)

        values.append(user_id)
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE users SET " + ", ".join(updates) + " WHERE user_id = ?",
                tuple(values),
            )
            if cursor.rowcount == 0:
                return None
            if is_active is False:
                connection.execute(
                    "DELETE FROM user_sessions WHERE user_id = ?",
                    (user_id,),
                )
        return self.get_user_by_id(user_id)

    def authenticate(self, email: str, password: str) -> dict | None:
        user = self.get_user_by_email(email)
        if not user or not bool(user["is_active"]):
            # Perform a scrypt operation even for unknown/inactive accounts so
            # account existence is less obvious from response timing.
            hashlib.scrypt(
                password.encode("utf-8"),
                salt=b"specra-invalid-account-salt",
                n=PASSWORD_SCRYPT_N,
                r=PASSWORD_SCRYPT_R,
                p=PASSWORD_SCRYPT_P,
                dklen=64,
            )
            return None
        if not verify_password(password, user["password_hash"]):
            return None
        return user

    def update_password(self, user_id: str, password: str) -> dict | None:
        encoded = hash_password(password)
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE users SET password_hash = ? WHERE user_id = ?",
                (encoded, user_id),
            )
            if cursor.rowcount == 0:
                return None
            # Rotate all sessions whenever credentials change.
            connection.execute(
                "DELETE FROM user_sessions WHERE user_id = ?",
                (user_id,),
            )
        return self.get_user_by_id(user_id)

    def create_session(self, user_id: str) -> tuple[str, datetime]:
        token = secrets.token_urlsafe(32)
        now = utc_now()
        expires_at = now + timedelta(hours=SESSION_HOURS)
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM user_sessions WHERE expires_at <= ?",
                (now.isoformat(),),
            )
            connection.execute(
                """
                INSERT INTO user_sessions (
                    session_hash, user_id, expires_at, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    _token_hash(token),
                    user_id,
                    expires_at.isoformat(),
                    now.isoformat(),
                ),
            )
        return token, expires_at

    def get_session_user(self, token: str | None) -> dict | None:
        if not token:
            return None
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT u.*
                FROM user_sessions s
                JOIN users u ON u.user_id = s.user_id
                WHERE s.session_hash = ? AND s.expires_at > ?
                """,
                (_token_hash(token), _now_text()),
            ).fetchone()
            if row is None or not bool(row["is_active"]):
                return None
            return dict(row)

    def revoke_session(self, token: str | None) -> None:
        if not token:
            return
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM user_sessions WHERE session_hash = ?",
                (_token_hash(token),),
            )

    @staticmethod
    def login_identity(email: str, client_host: str | None) -> str:
        value = f"{email.strip().casefold()}|{client_host or 'unknown'}"
        return _token_hash(value)

    def is_login_locked(self, identity_hash: str) -> bool:
        now = utc_now()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT locked_until FROM login_attempts WHERE identity_hash = ?",
                (identity_hash,),
            ).fetchone()
            if not row or not row["locked_until"]:
                return False
            try:
                return datetime.fromisoformat(row["locked_until"]) > now
            except ValueError:
                return False

    def record_login_failure(self, identity_hash: str) -> None:
        now = utc_now()
        window = timedelta(minutes=15)
        lock_duration = timedelta(minutes=15)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT failures, window_started_at FROM login_attempts WHERE identity_hash = ?",
                (identity_hash,),
            ).fetchone()
            if row:
                try:
                    started = datetime.fromisoformat(row["window_started_at"])
                except ValueError:
                    started = now
            else:
                started = now

            if not row or now - started > window:
                failures = 1
                started = now
            else:
                failures = int(row["failures"]) + 1

            locked_until = (
                (now + lock_duration).isoformat()
                if failures >= 5
                else None
            )
            connection.execute(
                """
                INSERT INTO login_attempts (
                    identity_hash, failures, window_started_at, locked_until
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(identity_hash) DO UPDATE SET
                    failures = excluded.failures,
                    window_started_at = excluded.window_started_at,
                    locked_until = excluded.locked_until
                """,
                (identity_hash, failures, started.isoformat(), locked_until),
            )

    def clear_login_failures(self, identity_hash: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM login_attempts WHERE identity_hash = ?",
                (identity_hash,),
            )

    def get_project_role(self, project_id: str, user: dict) -> str | None:
        if user.get("role") == "admin":
            return "admin"
        with self._connect() as connection:
            row = connection.execute(
                "SELECT owner_id FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if row is None:
                return None
            if row["owner_id"] == user["user_id"]:
                return "owner"
            member = connection.execute(
                """
                SELECT role FROM project_members
                WHERE project_id = ? AND user_id = ?
                """,
                (project_id, user["user_id"]),
            ).fetchone()
            return member["role"] if member else None

    def has_project_access(self, project_id: str, user: dict) -> bool:
        return self.get_project_role(project_id, user) is not None

    def add_project_member(
        self,
        *,
        project_id: str,
        email: str,
        role: str,
    ) -> dict:
        if role not in PROJECT_ROLES:
            raise ValueError(
                f"Project role must be one of: {', '.join(sorted(PROJECT_ROLES))}."
            )
        user = self.get_user_by_email(email)
        if not user or not bool(user["is_active"]):
            raise ValueError("No active Specra user exists with that email.")
        with self._connect() as connection:
            project = connection.execute(
                "SELECT project_id FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if project is None:
                raise ValueError("Project not found.")
            connection.execute(
                """
                INSERT INTO project_members(project_id, user_id, role, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(project_id, user_id) DO UPDATE SET
                    role = excluded.role
                """,
                (project_id, user["user_id"], role, _now_text()),
            )
        return {
            "project_id": project_id,
            "user_id": user["user_id"],
            "email": user["email"],
            "display_name": user["display_name"],
            "role": role,
        }

    def list_project_members(self, project_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    u.user_id,
                    u.email,
                    u.display_name,
                    'owner' AS role,
                    p.created_at
                FROM projects p
                JOIN users u ON u.user_id = p.owner_id
                WHERE p.project_id = ?

                UNION ALL

                SELECT
                    u.user_id,
                    u.email,
                    u.display_name,
                    pm.role,
                    pm.created_at
                FROM project_members pm
                JOIN users u ON u.user_id = pm.user_id
                JOIN projects p ON p.project_id = pm.project_id
                WHERE pm.project_id = ?
                  AND (p.owner_id IS NULL OR pm.user_id <> p.owner_id)

                ORDER BY 5 ASC
                """,
                (project_id, project_id),
            ).fetchall()
            return [dict(row) for row in rows]

    def remove_project_member(self, project_id: str, user_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM project_members WHERE project_id = ? AND user_id = ?",
                (project_id, user_id),
            )
            return cursor.rowcount > 0


auth_store = AuthStore()


def get_current_user(request: Request) -> dict:
    if not persistent_storage_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Specra is paused until durable storage is configured. "
                "Set DATABASE_URL in the backend environment before using authenticated endpoints."
            ),
        )
    token = request.cookies.get(AUTH_COOKIE_NAME)
    user = auth_store.get_session_user(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in to access Specra.",
        )
    return user


def require_roles(*roles: str) -> Callable:
    """Require one of the global account roles (admins bypass role restrictions)."""
    def dependency(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") != "admin" and user.get("role") not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account role does not permit this action.",
            )
        return user
    return dependency


def require_project_roles(*roles: str) -> Callable:
    """Require project membership and one of the assigned project roles."""
    def dependency(
        project_id: str,
        user: dict = Depends(get_current_user),
    ) -> dict:
        role = auth_store.get_project_role(project_id, user)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or you do not have access to it.",
            )
        if roles and role != "admin" and role != "owner" and role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your project role does not permit this action.",
            )
        return user
    return dependency


def require_stage_role() -> Callable:
    def dependency(
        project_id: str,
        stage: str,
        user: dict = Depends(get_current_user),
    ) -> dict:
        role = auth_store.get_project_role(project_id, user)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or you do not have access to it.",
            )
        if role in {"admin", "owner"}:
            return user
        required_role = STAGE_ROLE.get(stage.strip().casefold())
        if required_role is None or role not in {required_role, "analyst"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your project role does not permit regenerating this artifact.",
            )
        return user
    return dependency
