"""SQLite by default, with an optional shared PostgreSQL database for hosted deployments.

Set DATABASE_URL to a PostgreSQL connection URI in production. When the variable
is absent, local development and tests continue to use SQLite.

This compatibility adapter deliberately supports only the SQL subset used by
Specra's existing stores; it is not a general SQLite-to-PostgreSQL translator.
"""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Any


_POSTGRES_URL_PREFIXES = ("postgres://", "postgresql://")
_GENERATED_PRIMARY_KEYS = {
    "artifact_versions": "artifact_version_id",
    "project_events": "event_id",
    "project_test_suites": "suite_id",
    "project_copilot_messages": "message_id",
}


def database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def using_postgres() -> bool:
    url = database_url()
    return url.startswith(_POSTGRES_URL_PREFIXES)


def persistent_storage_required() -> bool:
    """Whether this deployment must use a shared database instead of local SQLite."""
    value = os.getenv("REQUIRE_PERSISTENT_DATABASE", "").strip().casefold()
    return value in {"1", "true", "yes", "on"}


def persistent_storage_configured() -> bool:
    """Whether a PostgreSQL URL is configured for hosted persistence."""
    return using_postgres()


def persistent_storage_ready() -> bool:
    """Allow SQLite for local development, but block hosted auth without PostgreSQL."""
    return not persistent_storage_required() or persistent_storage_configured()


def _translate_sql(sql: str) -> tuple[str, str | None]:
    """Translate the small set of SQLite-specific statements Specra uses."""
    statement = sql.strip()
    if re.fullmatch(r"PRAGMA\s+foreign_keys\s*=\s*ON", statement, re.IGNORECASE):
        return "SELECT 1", None

    table_info = re.fullmatch(
        r"PRAGMA\s+table_info\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)",
        statement,
        re.IGNORECASE,
    )
    if table_info:
        return (
            """
            SELECT
                ordinal_position AS cid,
                column_name AS name,
                data_type AS type,
                CASE WHEN is_nullable = 'NO' THEN 1 ELSE 0 END AS notnull,
                column_default AS dflt_value,
                0 AS pk
            FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = %s
            ORDER BY ordinal_position
            """,
            table_info.group(1).lower(),
        )

    # PostgreSQL uses sequences rather than SQLite AUTOINCREMENT.
    translated = re.sub(
        r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b",
        "BIGSERIAL PRIMARY KEY",
        statement,
        flags=re.IGNORECASE,
    )
    ignore_insert = bool(
        re.match(r"INSERT\s+OR\s+IGNORE\s+INTO\b", translated, re.IGNORECASE)
    )
    translated = re.sub(
        r"^INSERT\s+OR\s+IGNORE\s+INTO\b",
        "INSERT INTO",
        translated,
        flags=re.IGNORECASE,
    )
    translated = translated.replace("?", "%s")

    if ignore_insert and not re.search(r"\bON\s+CONFLICT\b", translated, re.IGNORECASE):
        translated = translated.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"

    return translated, None


class _PostgresCursor:
    def __init__(self, connection, cursor):
        self._connection = connection
        self._cursor = cursor
        self.lastrowid = None

    def execute(self, sql: str, parameters: Any = None):
        translated, pragma_parameter = _translate_sql(sql)
        args = (pragma_parameter,) if pragma_parameter is not None else parameters
        generated_key = None
        match = re.match(r"\s*INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)", translated, re.IGNORECASE)
        if match and not re.search(r"\bRETURNING\b", translated, re.IGNORECASE):
            generated_key = _GENERATED_PRIMARY_KEYS.get(match.group(1).lower())
            if generated_key:
                translated = translated.rstrip().rstrip(";") + f" RETURNING {generated_key}"

        try:
            if args is None:
                self._cursor.execute(translated)
            else:
                self._cursor.execute(translated, args)
        except Exception as exc:
            # Keep the existing stores' duplicate/foreign-key error handling
            # consistent between SQLite and PostgreSQL.
            try:
                import psycopg2
                if isinstance(exc, psycopg2.IntegrityError):
                    raise sqlite3.IntegrityError(str(exc)) from exc
            except ImportError:
                pass
            raise

        if generated_key:
            generated_row = self._cursor.fetchone()
            self.lastrowid = generated_row[0] if generated_row else None
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def description(self):
        return self._cursor.description

    def close(self):
        self._cursor.close()

    def __iter__(self):
        return iter(self._cursor)


class _PostgresConnection:
    def __init__(self, connection):
        self._connection = connection
        self.row_factory = None  # SQLite compatibility; DictCursor supplies named access.

    def execute(self, sql: str, parameters: Any = None):
        return _PostgresCursor(self._connection, self._connection.cursor()).execute(sql, parameters)

    def executemany(self, sql: str, parameter_rows):
        translated, pragma_parameter = _translate_sql(sql)
        if pragma_parameter is not None:
            raise ValueError("executemany is not supported for PRAGMA statements")
        cursor = self._connection.cursor()
        try:
            cursor.executemany(translated, parameter_rows)
        except Exception as exc:
            try:
                import psycopg2
                if isinstance(exc, psycopg2.IntegrityError):
                    raise sqlite3.IntegrityError(str(exc)) from exc
            except ImportError:
                pass
            raise
        return _PostgresCursor(self._connection, cursor)

    def cursor(self):
        return _PostgresCursor(self._connection, self._connection.cursor())

    def executescript(self, script: str):
        # The application's schema scripts contain ordinary DDL separated by
        # semicolons; there are no stored procedures or semicolons in literals.
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)
        self._connection.commit()

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()
        return False


def connect_database(
    db_path: str | Path,
    *,
    timeout: int = 30,
    check_same_thread: bool = True,
):
    """Connect to DATABASE_URL when configured, otherwise use a local SQLite file."""
    url = database_url()
    if not url:
        return sqlite3.connect(
            str(db_path),
            timeout=timeout,
            check_same_thread=check_same_thread,
        )
    if not url.startswith(_POSTGRES_URL_PREFIXES):
        raise RuntimeError(
            "DATABASE_URL must be a PostgreSQL connection URI. "
            "Unset it for local SQLite development."
        )

    try:
        import psycopg2
        from psycopg2.extras import DictCursor
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL storage is configured but psycopg2 is not installed. "
            "Install the backend requirements."
        ) from exc

    normalized_url = "postgresql://" + url[len("postgres://"):] if url.startswith("postgres://") else url
    connection = psycopg2.connect(
        normalized_url,
        connect_timeout=timeout,
        cursor_factory=DictCursor,
    )
    return _PostgresConnection(connection)
