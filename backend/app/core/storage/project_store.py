import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"
DEFAULT_DB_PATH = DATA_DIR / "studio.db"


STAGES = (
    "requirements",
    "project_plan",
    "architecture",
    "technical_review",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectStore:
    """
    Persistent SQLite storage for AI Development Studio.

    Stores:
    - project metadata
    - current project status
    - latest artifacts
    - artifact versions
    - workflow events

    SQLite is intentionally used for the MVP because it requires no
    database server and keeps the project state durable across backend
    restarts.
    """

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._lock = RLock()

        self._initialize_database()

    # ---------------------------------------------------------
    # Database
    # ---------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.db_path),
            timeout=30,
        )

        connection.row_factory = sqlite3.Row

        return connection

    def _initialize_database(self) -> None:
        with self._lock:
            connection = self._connect()

            try:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS projects (
                        project_id TEXT PRIMARY KEY,
                        idea TEXT NOT NULL,
                        project_name TEXT,
                        status TEXT NOT NULL,
                        current_stage TEXT NOT NULL,
                        stage_status TEXT NOT NULL,
                        approved INTEGER,
                        error TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS project_stages (
                        project_id TEXT PRIMARY KEY,
                        requirements_status TEXT NOT NULL,
                        project_plan_status TEXT NOT NULL,
                        architecture_status TEXT NOT NULL,
                        technical_review_status TEXT NOT NULL,
                        FOREIGN KEY(project_id)
                            REFERENCES projects(project_id)
                            ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS artifact_versions (
                        artifact_version_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT NOT NULL,
                        stage TEXT NOT NULL,
                        version_number INTEGER NOT NULL,
                        content_json TEXT NOT NULL,
                        instruction TEXT,
                        source TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(project_id)
                            REFERENCES projects(project_id)
                            ON DELETE CASCADE,
                        UNIQUE(
                            project_id,
                            stage,
                            version_number
                        )
                    );

                    CREATE TABLE IF NOT EXISTS project_events (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        stage TEXT,
                        message TEXT,
                        data_json TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(project_id)
                            REFERENCES projects(project_id)
                            ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS
                        idx_artifact_versions_project_stage
                    ON artifact_versions(
                        project_id,
                        stage,
                        version_number
                    );

                    CREATE INDEX IF NOT EXISTS
                        idx_project_events_project
                    ON project_events(
                        project_id,
                        event_id
                    );
                    """
                )

                connection.commit()

            finally:
                connection.close()

    # ---------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------

    @staticmethod
    def _empty_stages() -> dict[str, str]:
        return {
            stage: "waiting"
            for stage in STAGES
        }

    def _read_stages(
        self,
        connection: sqlite3.Connection,
        project_id: str,
    ) -> dict[str, str]:

        row = connection.execute(
            """
            SELECT
                requirements_status,
                project_plan_status,
                architecture_status,
                technical_review_status
            FROM project_stages
            WHERE project_id = ?
            """,
            (project_id,),
        ).fetchone()

        if row is None:
            return self._empty_stages()

        return {
            "requirements": row["requirements_status"],
            "project_plan": row["project_plan_status"],
            "architecture": row["architecture_status"],
            "technical_review": row[
                "technical_review_status"
            ],
        }

    def _ensure_stage_row(
        self,
        connection: sqlite3.Connection,
        project_id: str,
    ) -> None:

        connection.execute(
            """
            INSERT OR IGNORE INTO project_stages (
                project_id,
                requirements_status,
                project_plan_status,
                architecture_status,
                technical_review_status
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                project_id,
                "waiting",
                "waiting",
                "waiting",
                "waiting",
            ),
        )

    # ---------------------------------------------------------
    # Projects
    # ---------------------------------------------------------

    def create_project(
        self,
        *,
        project_id: str,
        idea: str,
        created_at: str | None = None,
    ) -> dict:

        now = created_at or _utc_now()

        with self._lock:
            connection = self._connect()

            try:
                connection.execute(
                    """
                    INSERT INTO projects (
                        project_id,
                        idea,
                        project_name,
                        status,
                        current_stage,
                        stage_status,
                        approved,
                        error,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        idea,
                        None,
                        "created",
                        "idle",
                        "idle",
                        None,
                        None,
                        now,
                        now,
                    ),
                )

                self._ensure_stage_row(
                    connection,
                    project_id,
                )

                self._add_event(
                    connection,
                    project_id=project_id,
                    event_type="project_created",
                    stage=None,
                    message="Project created.",
                    data=None,
                )

                connection.commit()

            finally:
                connection.close()

        return self.get_project(project_id)

    def get_project(
        self,
        project_id: str,
    ) -> dict | None:

        with self._lock:
            connection = self._connect()

            try:
                row = connection.execute(
                    """
                    SELECT *
                    FROM projects
                    WHERE project_id = ?
                    """,
                    (project_id,),
                ).fetchone()

                if row is None:
                    return None

                project = dict(row)

                project["approved"] = (
                    None
                    if row["approved"] is None
                    else bool(row["approved"])
                )

                project["stages"] = (
                    self._read_stages(
                        connection,
                        project_id,
                    )
                )

                project[
                    "artifact_versions"
                ] = self.get_latest_version_numbers(
                    project_id,
                    connection=connection,
                )

                return project

            finally:
                connection.close()

    def list_projects(
        self,
        limit: int = 50,
    ) -> list[dict]:

        safe_limit = max(
            1,
            min(limit, 200),
        )

        with self._lock:
            connection = self._connect()

            try:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM projects
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (safe_limit,),
                ).fetchall()

                projects = []

                for row in rows:
                    project = dict(row)

                    project["approved"] = (
                        None
                        if row["approved"] is None
                        else bool(row["approved"])
                    )

                    project["stages"] = (
                        self._read_stages(
                            connection,
                            row["project_id"],
                        )
                    )

                    project[
                        "artifact_versions"
                    ] = self.get_latest_version_numbers(
                        row["project_id"],
                        connection=connection,
                    )

                    projects.append(project)

                return projects

            finally:
                connection.close()

    def delete_project(
        self,
        project_id: str,
    ) -> bool:

        with self._lock:
            connection = self._connect()

            try:
                cursor = connection.execute(
                    """
                    DELETE FROM projects
                    WHERE project_id = ?
                    """,
                    (project_id,),
                )

                connection.commit()

                return cursor.rowcount > 0

            finally:
                connection.close()

    def update_project(
        self,
        project_id: str,
        **fields: Any,
    ) -> dict | None:

        allowed_fields = {
            "idea",
            "project_name",
            "status",
            "current_stage",
            "stage_status",
            "approved",
            "error",
            "updated_at",
        }

        updates = []

        values = []

        for field, value in fields.items():

            if field not in allowed_fields:
                raise ValueError(
                    f"Unknown project field: {field}"
                )

            updates.append(
                f"{field} = ?"
            )

            if field == "approved":
                if value is None:
                    values.append(None)
                else:
                    values.append(
                        1 if value else 0
                    )
            else:
                values.append(value)

        if not updates:
            return self.get_project(
                project_id
            )

        if "updated_at" not in fields:
            updates.append(
                "updated_at = ?"
            )
            values.append(
                _utc_now()
            )

        values.append(project_id)

        with self._lock:
            connection = self._connect()

            try:
                cursor = connection.execute(
                    f"""
                    UPDATE projects
                    SET {", ".join(updates)}
                    WHERE project_id = ?
                    """,
                    tuple(values),
                )

                connection.commit()

                if cursor.rowcount == 0:
                    return None

            finally:
                connection.close()

        return self.get_project(
            project_id
        )

    # ---------------------------------------------------------
    # Stage status
    # ---------------------------------------------------------

    def set_stage_status(
        self,
        project_id: str,
        stage: str,
        stage_status: str,
        *,
        current_stage: str | None = None,
        project_status: str | None = None,
        message: str | None = None,
    ) -> dict | None:

        if stage not in STAGES:
            raise ValueError(
                f"Unknown stage: {stage}"
            )

        stage_columns = {
            "requirements":
                "requirements_status",
            "project_plan":
                "project_plan_status",
            "architecture":
                "architecture_status",
            "technical_review":
                "technical_review_status",
        }

        column = stage_columns[stage]

        with self._lock:
            connection = self._connect()

            try:
                self._ensure_stage_row(
                    connection,
                    project_id,
                )

                connection.execute(
                    f"""
                    UPDATE project_stages
                    SET {column} = ?
                    WHERE project_id = ?
                    """,
                    (
                        stage_status,
                        project_id,
                    ),
                )

                project_updates = {
                    "stage_status": stage_status,
                }

                if current_stage is not None:
                    project_updates[
                        "current_stage"
                    ] = current_stage

                if project_status is not None:
                    project_updates[
                        "status"
                    ] = project_status

                update_parts = []
                update_values = []

                for field, value in project_updates.items():
                    update_parts.append(
                        f"{field} = ?"
                    )
                    update_values.append(value)

                update_parts.append(
                    "updated_at = ?"
                )
                update_values.append(
                    _utc_now()
                )

                update_values.append(
                    project_id
                )

                connection.execute(
                    f"""
                    UPDATE projects
                    SET {", ".join(update_parts)}
                    WHERE project_id = ?
                    """,
                    tuple(update_values),
                )

                self._add_event(
                    connection,
                    project_id=project_id,
                    event_type="stage_status",
                    stage=stage,
                    message=message
                    or f"{stage} -> {stage_status}",
                    data={
                        "status": stage_status,
                    },
                )

                connection.commit()

            finally:
                connection.close()

        return self.get_project(
            project_id
        )

    def reset_stage_statuses(
        self,
        project_id: str,
        stages: list[str] | tuple[str, ...],
        *,
        first_stage: str,
        project_status: str = "queued",
    ) -> dict | None:

        for stage in stages:
            if stage not in STAGES:
                raise ValueError(
                    f"Unknown stage: {stage}"
                )

        with self._lock:
            connection = self._connect()

            try:
                self._ensure_stage_row(
                    connection,
                    project_id,
                )

                column_map = {
                    "requirements":
                        "requirements_status",
                    "project_plan":
                        "project_plan_status",
                    "architecture":
                        "architecture_status",
                    "technical_review":
                        "technical_review_status",
                }

                for stage in stages:
                    connection.execute(
                        f"""
                        UPDATE project_stages
                        SET {column_map[stage]} = ?
                        WHERE project_id = ?
                        """,
                        (
                            "waiting",
                            project_id,
                        ),
                    )

                connection.execute(
                    f"""
                    UPDATE projects
                    SET
                        status = ?,
                        current_stage = ?,
                        stage_status = ?,
                        approved = NULL,
                        error = NULL,
                        updated_at = ?
                    WHERE project_id = ?
                    """,
                    (
                        project_status,
                        first_stage,
                        "queued",
                        _utc_now(),
                        project_id,
                    ),
                )

                self._add_event(
                    connection,
                    project_id=project_id,
                    event_type="operation_queued",
                    stage=first_stage,
                    message=(
                        "Project operation queued."
                    ),
                    data={
                        "affected_stages": list(stages),
                    },
                )

                connection.commit()

            finally:
                connection.close()

        return self.get_project(
            project_id
        )

    # ---------------------------------------------------------
    # Artifacts / versions
    # ---------------------------------------------------------

    def save_artifact(
        self,
        project_id: str,
        stage: str,
        content: dict,
        *,
        instruction: str | None = None,
        source: str = "agent",
    ) -> dict:

        if stage not in STAGES:
            raise ValueError(
                f"Unknown stage: {stage}"
            )

        content_json = json.dumps(
            content,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        with self._lock:
            connection = self._connect()

            try:
                latest_row = connection.execute(
                    """
                    SELECT MAX(version_number) AS latest_version
                    FROM artifact_versions
                    WHERE project_id = ?
                      AND stage = ?
                    """,
                    (
                        project_id,
                        stage,
                    ),
                ).fetchone()

                latest_version = (
                    latest_row["latest_version"]
                    or 0
                )

                version_number = (
                    latest_version + 1
                )

                created_at = _utc_now()

                cursor = connection.execute(
                    """
                    INSERT INTO artifact_versions (
                        project_id,
                        stage,
                        version_number,
                        content_json,
                        instruction,
                        source,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        stage,
                        version_number,
                        content_json,
                        instruction,
                        source,
                        created_at,
                    ),
                )

                self._add_event(
                    connection,
                    project_id=project_id,
                    event_type="artifact_saved",
                    stage=stage,
                    message=(
                        f"{stage} artifact saved as v{version_number}."
                    ),
                    data={
                        "version": version_number,
                        "source": source,
                        "instruction": instruction,
                    },
                )

                connection.execute(
                    """
                    UPDATE projects
                    SET updated_at = ?
                    WHERE project_id = ?
                    """,
                    (
                        created_at,
                        project_id,
                    ),
                )

                connection.commit()

                return {
                    "artifact_version_id":
                        cursor.lastrowid,
                    "project_id":
                        project_id,
                    "stage":
                        stage,
                    "version_number":
                        version_number,
                    "content":
                        content,
                    "instruction":
                        instruction,
                    "source":
                        source,
                    "created_at":
                        created_at,
                }

            finally:
                connection.close()

    def get_latest_artifact(
        self,
        project_id: str,
        stage: str,
    ) -> dict | None:

        with self._lock:
            connection = self._connect()

            try:
                row = connection.execute(
                    """
                    SELECT *
                    FROM artifact_versions
                    WHERE project_id = ?
                      AND stage = ?
                    ORDER BY version_number DESC
                    LIMIT 1
                    """,
                    (
                        project_id,
                        stage,
                    ),
                ).fetchone()

                if row is None:
                    return None

                return self._artifact_row_to_dict(
                    row
                )

            finally:
                connection.close()

    def get_artifacts(
        self,
        project_id: str,
    ) -> dict[str, dict | None]:

        result = {}

        for stage in STAGES:
            artifact = (
                self.get_latest_artifact(
                    project_id,
                    stage,
                )
            )

            result[stage] = (
                artifact["content"]
                if artifact
                else None
            )

        return result

    def get_artifact_versions(
        self,
        project_id: str,
        stage: str,
    ) -> list[dict]:

        if stage not in STAGES:
            raise ValueError(
                f"Unknown stage: {stage}"
            )

        with self._lock:
            connection = self._connect()

            try:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM artifact_versions
                    WHERE project_id = ?
                      AND stage = ?
                    ORDER BY version_number DESC
                    """,
                    (
                        project_id,
                        stage,
                    ),
                ).fetchall()

                return [
                    self._artifact_row_to_dict(
                        row
                    )
                    for row in rows
                ]

            finally:
                connection.close()

    def get_all_versions(
        self,
        project_id: str,
    ) -> dict[str, list[dict]]:

        return {
            stage: self.get_artifact_versions(
                project_id,
                stage,
            )
            for stage in STAGES
        }

    def get_latest_version_numbers(
        self,
        project_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> dict[str, int]:

        own_connection = (
            connection is None
        )

        if own_connection:
            connection = self._connect()

        try:
            rows = connection.execute(
                """
                SELECT
                    stage,
                    MAX(version_number) AS latest_version
                FROM artifact_versions
                WHERE project_id = ?
                GROUP BY stage
                """,
                (project_id,),
            ).fetchall()

            result = {
                stage: 0
                for stage in STAGES
            }

            for row in rows:
                result[row["stage"]] = (
                    row["latest_version"]
                )

            return result

        finally:
            if own_connection:
                connection.close()

    @staticmethod
    def _artifact_row_to_dict(
        row: sqlite3.Row,
    ) -> dict:

        return {
            "artifact_version_id":
                row["artifact_version_id"],
            "project_id":
                row["project_id"],
            "stage":
                row["stage"],
            "version_number":
                row["version_number"],
            "content":
                json.loads(
                    row["content_json"]
                ),
            "instruction":
                row["instruction"],
            "source":
                row["source"],
            "created_at":
                row["created_at"],
        }

    # ---------------------------------------------------------
    # Events / audit history
    # ---------------------------------------------------------

    def add_event(
        self,
        project_id: str,
        event_type: str,
        *,
        stage: str | None = None,
        message: str | None = None,
        data: dict | None = None,
    ) -> None:

        with self._lock:
            connection = self._connect()

            try:
                self._add_event(
                    connection,
                    project_id=project_id,
                    event_type=event_type,
                    stage=stage,
                    message=message,
                    data=data,
                )

                connection.commit()

            finally:
                connection.close()

    @staticmethod
    def _add_event(
        connection: sqlite3.Connection,
        *,
        project_id: str,
        event_type: str,
        stage: str | None,
        message: str | None,
        data: dict | None,
    ) -> None:

        data_json = (
            json.dumps(
                data,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            if data is not None
            else None
        )

        connection.execute(
            """
            INSERT INTO project_events (
                project_id,
                event_type,
                stage,
                message,
                data_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                event_type,
                stage,
                message,
                data_json,
                _utc_now(),
            ),
        )

    def get_events(
        self,
        project_id: str,
        limit: int = 100,
    ) -> list[dict]:

        safe_limit = max(
            1,
            min(limit, 500),
        )

        with self._lock:
            connection = self._connect()

            try:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM project_events
                    WHERE project_id = ?
                    ORDER BY event_id DESC
                    LIMIT ?
                    """,
                    (
                        project_id,
                        safe_limit,
                    ),
                ).fetchall()

                events = []

                for row in rows:
                    events.append(
                        {
                            "event_id":
                                row["event_id"],
                            "project_id":
                                row["project_id"],
                            "event_type":
                                row["event_type"],
                            "stage":
                                row["stage"],
                            "message":
                                row["message"],
                            "data":
                                (
                                    json.loads(
                                        row["data_json"]
                                    )
                                    if row["data_json"]
                                    else None
                                ),
                            "created_at":
                                row["created_at"],
                        }
                    )

                return events

            finally:
                connection.close()

    # ---------------------------------------------------------
    # Restart recovery
    # ---------------------------------------------------------

    def mark_interrupted_projects(
        self,
    ) -> int:

        with self._lock:
            connection = self._connect()

            try:
                rows = connection.execute(
                    """
                    SELECT project_id
                    FROM projects
                    WHERE status IN ('queued', 'running')
                    """
                ).fetchall()

                if not rows:
                    return 0

                for row in rows:
                    project_id = (
                        row["project_id"]
                    )

                    connection.execute(
                        """
                        UPDATE projects
                        SET
                            status = 'interrupted',
                            stage_status = 'interrupted',
                            error = ?,
                            updated_at = ?
                        WHERE project_id = ?
                        """,
                        (
                            (
                                "Backend process restarted while "
                                "this workflow was running. Existing "
                                "artifacts and version history were "
                                "preserved. Run the project again "
                                "to continue."
                            ),
                            _utc_now(),
                            project_id,
                        ),
                    )

                    self._add_event(
                        connection,
                        project_id=project_id,
                        event_type="workflow_interrupted",
                        stage=None,
                        message=(
                            "Workflow interrupted by backend restart."
                        ),
                        data=None,
                    )

                connection.commit()

                return len(rows)

            finally:
                connection.close()


project_store = ProjectStore()