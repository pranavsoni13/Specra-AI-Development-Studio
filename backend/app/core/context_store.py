from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from app.core.database import connect_database


BASE_DIR = Path(__file__).resolve().parents[2]
CONTEXT_DB_PATH = BASE_DIR / "context.db"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectContextStore:
    """
    Persistent project-scoped context store.

    Context is intentionally kept separate from generated artifacts:
    artifacts are versioned engineering outputs, while context contains
    user-provided source material used to inform future agents.
    """

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or CONTEXT_DB_PATH
        self._lock = Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = connect_database(
            self.db_path,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS project_context (
                    context_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_project_context_project
                ON project_context(project_id)
                """
            )

            connection.commit()

    def list_context(
        self,
        project_id: str,
    ) -> list[dict]:
        with self._lock:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT
                        context_id,
                        project_id,
                        name,
                        kind,
                        content,
                        metadata,
                        created_at,
                        updated_at
                    FROM project_context
                    WHERE project_id = ?
                    ORDER BY updated_at DESC
                    """,
                    (project_id,),
                ).fetchall()

        return [
            self._deserialize_row(row)
            for row in rows
        ]

    def get_context(
        self,
        project_id: str,
        context_id: str,
    ) -> dict | None:
        with self._lock:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT
                        context_id,
                        project_id,
                        name,
                        kind,
                        content,
                        metadata,
                        created_at,
                        updated_at
                    FROM project_context
                    WHERE project_id = ?
                      AND context_id = ?
                    """,
                    (
                        project_id,
                        context_id,
                    ),
                ).fetchone()

        if row is None:
            return None

        return self._deserialize_row(row)

    def create_context(
        self,
        project_id: str,
        *,
        name: str,
        kind: str,
        content: str,
        metadata: dict | None = None,
    ) -> dict:
        context_id = str(uuid4())
        timestamp = _utc_now()
        metadata = metadata or {}

        record = {
            "context_id": context_id,
            "project_id": project_id,
            "name": name.strip(),
            "kind": kind.strip().lower(),
            "content": content,
            "metadata": metadata,
            "created_at": timestamp,
            "updated_at": timestamp,
        }

        with self._lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO project_context (
                        context_id,
                        project_id,
                        name,
                        kind,
                        content,
                        metadata,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["context_id"],
                        record["project_id"],
                        record["name"],
                        record["kind"],
                        record["content"],
                        json.dumps(
                            record["metadata"],
                            ensure_ascii=False,
                        ),
                        record["created_at"],
                        record["updated_at"],
                    ),
                )
                connection.commit()

        return record

    def update_context(
        self,
        project_id: str,
        context_id: str,
        *,
        name: str,
        kind: str,
        content: str,
        metadata: dict | None = None,
    ) -> dict | None:
        timestamp = _utc_now()
        metadata = metadata or {}

        with self._lock:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    UPDATE project_context
                    SET
                        name = ?,
                        kind = ?,
                        content = ?,
                        metadata = ?,
                        updated_at = ?
                    WHERE project_id = ?
                      AND context_id = ?
                    """,
                    (
                        name.strip(),
                        kind.strip().lower(),
                        content,
                        json.dumps(
                            metadata,
                            ensure_ascii=False,
                        ),
                        timestamp,
                        project_id,
                        context_id,
                    ),
                )
                connection.commit()

                if cursor.rowcount == 0:
                    return None

        return self.get_context(
            project_id,
            context_id,
        )

    def delete_context(
        self,
        project_id: str,
        context_id: str,
    ) -> bool:
        with self._lock:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    DELETE FROM project_context
                    WHERE project_id = ?
                      AND context_id = ?
                    """,
                    (
                        project_id,
                        context_id,
                    ),
                )
                connection.commit()

        return cursor.rowcount > 0

    def search_context(
        self,
        project_id: str,
        query: str,
        *,
        limit: int = 8,
    ) -> list[dict]:
        normalized_query = query.strip().casefold()

        if not normalized_query:
            return []

        context_items = self.list_context(
            project_id
        )

        tokens = [
            token
            for token in normalized_query.split()
            if len(token) > 1
        ]

        scored: list[tuple[int, dict]] = []

        for item in context_items:
            haystack = " ".join(
                [
                    item["name"],
                    item["kind"],
                    item["content"],
                ]
            ).casefold()

            score = 0

            if normalized_query in haystack:
                score += 10

            for token in tokens:
                if token in haystack:
                    score += 1

            if score > 0:
                scored.append(
                    (
                        score,
                        item,
                    )
                )

        scored.sort(
            key=lambda pair: (
                -pair[0],
                pair[1]["updated_at"],
            )
        )

        return [
            item
            for _, item in scored[:limit]
        ]

    @staticmethod
    def _deserialize_row(
        row: sqlite3.Row,
    ) -> dict:
        try:
            metadata = json.loads(
                row["metadata"] or "{}"
            )
        except json.JSONDecodeError:
            metadata = {}

        return {
            "context_id": row["context_id"],
            "project_id": row["project_id"],
            "name": row["name"],
            "kind": row["kind"],
            "content": row["content"],
            "metadata": metadata,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


project_context_store = ProjectContextStore()
