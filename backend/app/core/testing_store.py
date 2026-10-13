"""Versioned test-suite storage and manual execution results for Specra."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from app.core.storage.project_store import DEFAULT_DB_PATH


ALLOWED_STATUSES = {"not_run", "passed", "failed", "blocked"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TestStore:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path), timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_database(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS project_test_suites (
                    suite_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    suite_version INTEGER NOT NULL,
                    project_name TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    cases_json TEXT NOT NULL,
                    requirement_coverage_json TEXT NOT NULL,
                    coverage_warnings_json TEXT NOT NULL,
                    generation_model TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(project_id, suite_version),
                    FOREIGN KEY(project_id) REFERENCES projects(project_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS project_test_results (
                    suite_id INTEGER NOT NULL,
                    test_id TEXT NOT NULL,
                    status TEXT NOT NULL
                        CHECK(status IN ('not_run', 'passed', 'failed', 'blocked')),
                    execution_notes TEXT,
                    environment TEXT,
                    executed_at TEXT,
                    executed_by TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(suite_id, test_id),
                    FOREIGN KEY(suite_id) REFERENCES project_test_suites(suite_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_project_test_suites_project
                    ON project_test_suites(project_id, suite_version DESC);
                """
            )

    def save_suite(
        self,
        *,
        project_id: str,
        suite: dict,
        generation_model: str | None = None,
    ) -> dict:
        with self._lock, self._connect() as connection:
            project = connection.execute(
                "SELECT project_id FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if project is None:
                raise ValueError("Project not found.")

            connection.execute("BEGIN IMMEDIATE")
            latest = connection.execute(
                "SELECT MAX(suite_version) AS version FROM project_test_suites WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            version = int(latest["version"] or 0) + 1
            cursor = connection.execute(
                """
                INSERT INTO project_test_suites (
                    project_id, suite_version, project_name, summary,
                    cases_json, requirement_coverage_json,
                    coverage_warnings_json, generation_model, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    version,
                    str(suite.get("project_name") or "Untitled project"),
                    str(suite.get("summary") or ""),
                    json.dumps(suite.get("cases") or [], ensure_ascii=False),
                    json.dumps(suite.get("requirement_coverage") or []),
                    json.dumps(suite.get("coverage_warnings") or [], ensure_ascii=False),
                    generation_model,
                    _now(),
                ),
            )
            suite_id = int(cursor.lastrowid)
            connection.commit()
            return self.get_suite(project_id, suite_id=suite_id)

    def get_suite(
        self,
        project_id: str,
        *,
        suite_id: int | None = None,
    ) -> dict | None:
        with self._connect() as connection:
            if suite_id is None:
                row = connection.execute(
                    """
                    SELECT * FROM project_test_suites
                    WHERE project_id = ?
                    ORDER BY suite_version DESC
                    LIMIT 1
                    """,
                    (project_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT * FROM project_test_suites
                    WHERE project_id = ? AND suite_id = ?
                    """,
                    (project_id, suite_id),
                ).fetchone()

            if row is None:
                return None

            payload = {
                "suite_id": row["suite_id"],
                "project_id": row["project_id"],
                "suite_version": row["suite_version"],
                "project_name": row["project_name"],
                "summary": row["summary"],
                "cases": json.loads(row["cases_json"]),
                "requirement_coverage": json.loads(
                    row["requirement_coverage_json"]
                ),
                "coverage_warnings": json.loads(
                    row["coverage_warnings_json"]
                ),
                "generation_model": row["generation_model"],
                "created_at": row["created_at"],
            }
            result_rows = connection.execute(
                """
                SELECT * FROM project_test_results
                WHERE suite_id = ?
                """,
                (row["suite_id"],),
            ).fetchall()
            results = {item["test_id"]: dict(item) for item in result_rows}

            for case in payload["cases"]:
                result = results.get(case["test_id"])
                case.setdefault("status", "not_run")
                if result:
                    case.update(
                        status=result["status"],
                        execution_notes=result["execution_notes"],
                        environment=result["environment"],
                        executed_at=result["executed_at"],
                        executed_by=result["executed_by"],
                    )
            return payload

    def list_history(self, project_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT suite_id, suite_version, project_name, summary,
                       generation_model, created_at, cases_json
                FROM project_test_suites
                WHERE project_id = ?
                ORDER BY suite_version DESC
                """,
                (project_id,),
            ).fetchall()
            return [
                {
                    "suite_id": row["suite_id"],
                    "suite_version": row["suite_version"],
                    "project_name": row["project_name"],
                    "summary": row["summary"],
                    "generation_model": row["generation_model"],
                    "created_at": row["created_at"],
                    "case_count": len(json.loads(row["cases_json"])),
                }
                for row in rows
            ]

    def update_result(
        self,
        *,
        project_id: str,
        test_id: str,
        status: str,
        execution_notes: str | None,
        environment: str | None,
        executed_by: str,
    ) -> dict | None:
        if status not in ALLOWED_STATUSES:
            raise ValueError(
                f"Status must be one of: {', '.join(sorted(ALLOWED_STATUSES))}."
            )

        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT suite_id, cases_json
                FROM project_test_suites
                WHERE project_id = ?
                ORDER BY suite_version DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            if row is None:
                return None

            cases = json.loads(row["cases_json"])
            if not any(case.get("test_id") == test_id for case in cases):
                return None

            now = _now()
            did_execute = status != "not_run"
            connection.execute(
                """
                INSERT INTO project_test_results (
                    suite_id, test_id, status, execution_notes, environment,
                    executed_at, executed_by, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(suite_id, test_id) DO UPDATE SET
                    status = excluded.status,
                    execution_notes = excluded.execution_notes,
                    environment = excluded.environment,
                    executed_at = excluded.executed_at,
                    executed_by = excluded.executed_by,
                    updated_at = excluded.updated_at
                """,
                (
                    row["suite_id"],
                    test_id,
                    status,
                    execution_notes,
                    environment,
                    now if did_execute else None,
                    executed_by if did_execute else None,
                    now,
                ),
            )

        return self.get_suite(project_id)

    def delete_project_tests(self, project_id: str) -> None:
        """Explicit helper for data cleanup and test isolation."""
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM project_test_suites WHERE project_id = ?",
                (project_id,),
            )


test_store = TestStore()
