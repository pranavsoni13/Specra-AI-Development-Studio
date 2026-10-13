"""Private, project-scoped Copilot conversations in Specra's SQLite store."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4

from app.core.storage.project_store import DEFAULT_DB_PATH


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CopilotStore:
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
                CREATE TABLE IF NOT EXISTS project_copilot_conversations (
                    conversation_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(project_id)
                        ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS project_copilot_messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    source_refs_json TEXT NOT NULL DEFAULT '[]',
                    proposed_changes_json TEXT NOT NULL DEFAULT '[]',
                    model_name TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(conversation_id)
                        REFERENCES project_copilot_conversations(conversation_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_copilot_conversation_owner
                    ON project_copilot_conversations(project_id, user_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_copilot_messages_conversation
                    ON project_copilot_messages(conversation_id, message_id);
                """
            )

    def create_conversation(
        self,
        *,
        project_id: str,
        user_id: str,
        first_question: str,
    ) -> dict:
        conversation_id = str(uuid4())
        timestamp = _now()
        title = " ".join(first_question.split())[:96] or "New project conversation"
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO project_copilot_conversations(
                    conversation_id, project_id, user_id, title, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (conversation_id, project_id, user_id, title, timestamp, timestamp),
            )
        return self.get_conversation(
            project_id=project_id,
            user_id=user_id,
            conversation_id=conversation_id,
        )

    def get_conversation(
        self,
        *,
        project_id: str,
        user_id: str,
        conversation_id: str,
    ) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM project_copilot_conversations
                WHERE conversation_id = ? AND project_id = ? AND user_id = ?
                """,
                (conversation_id, project_id, user_id),
            ).fetchone()
            if row is None:
                return None
            messages = connection.execute(
                """
                SELECT message_id, role, content, source_refs_json,
                       proposed_changes_json, model_name, created_at
                FROM project_copilot_messages
                WHERE conversation_id = ?
                ORDER BY message_id ASC
                """,
                (conversation_id,),
            ).fetchall()

        return {
            "conversation_id": row["conversation_id"],
            "project_id": row["project_id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "messages": [
                {
                    "message_id": message["message_id"],
                    "role": message["role"],
                    "content": message["content"],
                    "source_refs": json.loads(message["source_refs_json"]),
                    "proposed_changes": json.loads(message["proposed_changes_json"]),
                    "model_name": message["model_name"],
                    "created_at": message["created_at"],
                }
                for message in messages
            ],
        }

    def append_exchange(
        self,
        *,
        conversation_id: str,
        project_id: str,
        user_id: str,
        question: str,
        answer: dict,
    ) -> dict | None:
        timestamp = _now()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT conversation_id FROM project_copilot_conversations
                WHERE conversation_id = ? AND project_id = ? AND user_id = ?
                """,
                (conversation_id, project_id, user_id),
            ).fetchone()
            if row is None:
                connection.rollback()
                return None

            connection.execute(
                """
                INSERT INTO project_copilot_messages(
                    conversation_id, role, content, source_refs_json,
                    proposed_changes_json, model_name, created_at
                ) VALUES (?, 'user', ?, '[]', '[]', NULL, ?)
                """,
                (conversation_id, question, timestamp),
            )
            connection.execute(
                """
                INSERT INTO project_copilot_messages(
                    conversation_id, role, content, source_refs_json,
                    proposed_changes_json, model_name, created_at
                ) VALUES (?, 'assistant', ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    answer["answer"],
                    json.dumps(answer.get("source_refs") or [], ensure_ascii=False),
                    json.dumps(answer.get("proposed_changes") or [], ensure_ascii=False),
                    answer.get("model_name"),
                    _now(),
                ),
            )
            connection.execute(
                """
                UPDATE project_copilot_conversations
                SET updated_at = ?
                WHERE conversation_id = ?
                """,
                (_now(), conversation_id),
            )
            connection.commit()

        return self.get_conversation(
            project_id=project_id,
            user_id=user_id,
            conversation_id=conversation_id,
        )

    def list_conversations(
        self,
        *,
        project_id: str,
        user_id: str,
        limit: int = 20,
    ) -> list[dict]:
        safe_limit = max(1, min(limit, 50))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT c.conversation_id, c.title, c.created_at, c.updated_at,
                       COUNT(m.message_id) AS message_count
                FROM project_copilot_conversations c
                LEFT JOIN project_copilot_messages m
                    ON m.conversation_id = c.conversation_id
                WHERE c.project_id = ? AND c.user_id = ?
                GROUP BY c.conversation_id
                ORDER BY c.updated_at DESC
                LIMIT ?
                """,
                (project_id, user_id, safe_limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_conversation(
        self,
        *,
        project_id: str,
        user_id: str,
        conversation_id: str,
    ) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM project_copilot_conversations
                WHERE conversation_id = ? AND project_id = ? AND user_id = ?
                """,
                (conversation_id, project_id, user_id),
            )
            return cursor.rowcount > 0


copilot_store = CopilotStore()
