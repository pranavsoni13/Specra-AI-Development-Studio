"""Versioned storage for generated, unexecuted source bundles."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4

from app.core.storage.project_store import DEFAULT_DB_PATH
from app.core.database import connect_database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CodeBundleStore:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        connection = connect_database(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_database(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS project_code_bundles (
                    bundle_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    bundle_version INTEGER NOT NULL,
                    bundle_json TEXT NOT NULL,
                    generation_model TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(project_id, bundle_version),
                    FOREIGN KEY(project_id) REFERENCES projects(project_id)
                        ON DELETE CASCADE,
                    FOREIGN KEY(created_by) REFERENCES users(user_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_project_code_bundles_history
                    ON project_code_bundles(project_id, bundle_version DESC);
                """
            )

    def save_bundle(
        self,
        *,
        project_id: str,
        created_by: str,
        bundle: dict,
        generation_model: str | None,
    ) -> dict:
        bundle_id = str(uuid4())
        timestamp = _now()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            project = connection.execute(
                "SELECT project_id FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if project is None:
                connection.rollback()
                raise ValueError("Project not found.")

            owner = connection.execute(
                "SELECT user_id FROM users WHERE user_id = ? AND is_active = 1",
                (created_by,),
            ).fetchone()
            if owner is None:
                connection.rollback()
                raise ValueError("Active account not found.")

            row = connection.execute(
                "SELECT MAX(bundle_version) AS version FROM project_code_bundles WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            version = int(row["version"] or 0) + 1
            connection.execute(
                """
                INSERT INTO project_code_bundles(
                    bundle_id, project_id, created_by, bundle_version,
                    bundle_json, generation_model, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bundle_id,
                    project_id,
                    created_by,
                    version,
                    json.dumps(bundle, ensure_ascii=False),
                    generation_model,
                    timestamp,
                ),
            )
            connection.commit()

        return self.get_bundle(project_id=project_id, bundle_id=bundle_id)

    def get_bundle(
        self,
        *,
        project_id: str,
        bundle_id: str,
    ) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT bundle_id, project_id, created_by, bundle_version,
                       bundle_json, generation_model, created_at
                FROM project_code_bundles
                WHERE project_id = ? AND bundle_id = ?
                """,
                (project_id, bundle_id),
            ).fetchone()
        if row is None:
            return None
        bundle = json.loads(row["bundle_json"])
        return {
            **bundle,
            "bundle_id": row["bundle_id"],
            "project_id": row["project_id"],
            "created_by": row["created_by"],
            "bundle_version": row["bundle_version"],
            "generation_model": row["generation_model"],
            "created_at": row["created_at"],
        }

    def get_latest_bundle(self, project_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT bundle_id
                FROM project_code_bundles
                WHERE project_id = ?
                ORDER BY bundle_version DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
        if row is None:
            return None
        return self.get_bundle(project_id=project_id, bundle_id=row["bundle_id"])

    def list_bundles(self, project_id: str, limit: int = 20) -> list[dict]:
        safe_limit = max(1, min(limit, 50))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT bundle_id, project_id, created_by, bundle_version,
                       bundle_json, generation_model, created_at
                FROM project_code_bundles
                WHERE project_id = ?
                ORDER BY bundle_version DESC
                LIMIT ?
                """,
                (project_id, safe_limit),
            ).fetchall()
        results = []
        for row in rows:
            bundle = json.loads(row["bundle_json"])
            results.append({
                "bundle_id": row["bundle_id"],
                "project_id": row["project_id"],
                "created_by": row["created_by"],
                "bundle_version": row["bundle_version"],
                "project_name": bundle.get("project_name", "Untitled project"),
                "summary": bundle.get("summary", ""),
                "stack": bundle.get("stack", "fastapi-react"),
                "file_count": len(bundle.get("files", [])),
                "validation_status": bundle.get("validation_status", "needs_review"),
                "execution_status": bundle.get("execution_status", "not_executed"),
                "generation_model": row["generation_model"],
                "created_at": row["created_at"],
            })
        return results


code_bundle_store = CodeBundleStore()
