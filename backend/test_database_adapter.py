from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.database import (
    _translate_sql,
    connect_database,
    persistent_storage_configured,
    persistent_storage_ready,
    persistent_storage_required,
    using_postgres,
)


class DatabaseAdapterTests(unittest.TestCase):
    def test_absent_database_url_keeps_local_sqlite_behavior(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"DATABASE_URL": ""}):
            path = Path(folder) / "local.sqlite3"
            connection = connect_database(path)
            try:
                self.assertIsInstance(connection, sqlite3.Connection)
                connection.execute("CREATE TABLE sample (sample_id TEXT PRIMARY KEY, label TEXT)")
                connection.execute("INSERT INTO sample (sample_id, label) VALUES (?, ?)", ("one", "local"))
                row = connection.execute("SELECT label FROM sample WHERE sample_id = ?", ("one",)).fetchone()
                self.assertEqual(row[0], "local")
            finally:
                connection.close()

    def test_hosted_storage_required_blocks_auth_until_database_url_exists(self):
        with patch.dict(os.environ, {"REQUIRE_PERSISTENT_DATABASE": "true", "DATABASE_URL": ""}):
            self.assertTrue(persistent_storage_required())
            self.assertFalse(persistent_storage_configured())
            self.assertFalse(persistent_storage_ready())

    def test_local_sqlite_fallback_remains_available_for_development(self):
        with patch.dict(os.environ, {"REQUIRE_PERSISTENT_DATABASE": "false", "DATABASE_URL": ""}):
            self.assertFalse(persistent_storage_required())
            self.assertFalse(persistent_storage_configured())
            self.assertTrue(persistent_storage_ready())

    def test_hosted_postgres_url_unlocks_storage_guard(self):
        with patch.dict(os.environ, {"REQUIRE_PERSISTENT_DATABASE": "true", "DATABASE_URL": "postgresql://user:password@host.example/db"}):
            self.assertTrue(persistent_storage_required())
            self.assertTrue(persistent_storage_configured())
            self.assertTrue(persistent_storage_ready())

    def test_postgres_url_detection_does_not_connect_to_network(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:password@host.example/db"}):
            self.assertTrue(using_postgres())

    def test_sqlite_placeholders_translate_to_postgres_placeholders(self):
        statement, parameter = _translate_sql("SELECT * FROM users WHERE email = ? AND is_active = ?")
        self.assertEqual(statement, "SELECT * FROM users WHERE email = %s AND is_active = %s")
        self.assertIsNone(parameter)

    def test_autoincrement_primary_keys_translate_to_bigserial(self):
        statement, _ = _translate_sql(
            "CREATE TABLE example (event_id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT)"
        )
        self.assertIn("BIGSERIAL PRIMARY KEY", statement)
        self.assertNotIn("AUTOINCREMENT", statement)

    def test_insert_or_ignore_translates_to_on_conflict(self):
        statement, _ = _translate_sql(
            "INSERT OR IGNORE INTO project_stages (project_id) VALUES (?)"
        )
        self.assertTrue(statement.startswith("INSERT INTO project_stages"))
        self.assertIn("ON CONFLICT DO NOTHING", statement)
        self.assertIn("VALUES (%s)", statement)

    def test_foreign_key_pragma_is_ignored_for_postgres(self):
        statement, parameter = _translate_sql("PRAGMA foreign_keys = ON")
        self.assertEqual(statement, "SELECT 1")
        self.assertIsNone(parameter)

    def test_table_info_pragma_maps_to_information_schema(self):
        statement, parameter = _translate_sql("PRAGMA table_info(projects)")
        self.assertIn("information_schema.columns", statement)
        self.assertEqual(parameter, "projects")

    def test_invalid_database_url_fails_clearly(self):
        with patch.dict(os.environ, {"DATABASE_URL": "mysql://user:password@host/db"}):
            with self.assertRaisesRegex(RuntimeError, "DATABASE_URL must be a PostgreSQL"):
                connect_database(Path("unused.sqlite3"))


if __name__ == "__main__":
    unittest.main()
