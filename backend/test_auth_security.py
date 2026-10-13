"""Deterministic tests for Specra login, sessions and project-role data."""
import tempfile
import unittest
from pathlib import Path

from app.core.security import AuthStore, hash_password, verify_password
from app.core.storage.project_store import ProjectStore


class PasswordSecurityTests(unittest.TestCase):
    def test_password_hash_round_trip_and_minimum_length(self):
        encoded = hash_password("correct horse battery")
        self.assertTrue(encoded.startswith("scrypt$"))
        self.assertTrue(verify_password("correct horse battery", encoded))
        self.assertFalse(verify_password("incorrect password", encoded))
        with self.assertRaisesRegex(ValueError, "12 characters"):
            hash_password("short")


class AuthStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "specra-test.sqlite3"
        self.projects = ProjectStore(self.db_path)
        self.auth = AuthStore(self.db_path)

    def tearDown(self):
        self.temp.cleanup()

    def test_session_tokens_are_opaque_expiring_and_revocable(self):
        user = self.auth.create_user(
            email="Alice@Example.com",
            display_name="Alice",
            password="correct horse battery",
            role="analyst",
        )
        token, expires_at = self.auth.create_session(user["user_id"])
        self.assertGreater(expires_at.timestamp(), 0)
        self.assertEqual(
            self.auth.get_session_user(token)["user_id"],
            user["user_id"],
        )
        self.assertNotEqual(token, self.auth._token_hash(token))
        with self.auth._connect() as connection:
            stored = connection.execute(
                "SELECT session_hash FROM user_sessions"
            ).fetchone()[0]
        self.assertNotEqual(stored, token)
        self.auth.revoke_session(token)
        self.assertIsNone(self.auth.get_session_user(token))

    def test_login_attempt_throttle_locks_after_five_failures(self):
        identity = self.auth.login_identity("alice@example.com", "127.0.0.1")
        self.assertFalse(self.auth.is_login_locked(identity))
        for _ in range(5):
            self.auth.record_login_failure(identity)
        self.assertTrue(self.auth.is_login_locked(identity))
        self.auth.clear_login_failures(identity)
        self.assertFalse(self.auth.is_login_locked(identity))

    def test_project_lists_are_scoped_to_owner_or_membership(self):
        owner = self.auth.create_user(
            email="owner@example.com",
            display_name="Owner",
            password="owner password long",
            role="analyst",
        )
        reviewer = self.auth.create_user(
            email="reviewer@example.com",
            display_name="Reviewer",
            password="reviewer password long",
            role="reviewer",
        )
        stranger = self.auth.create_user(
            email="stranger@example.com",
            display_name="Stranger",
            password="stranger password long",
            role="viewer",
        )
        first = self.projects.create_project(
            project_id="owned-by-owner",
            idea="First project",
            owner_id=owner["user_id"],
        )
        second = self.projects.create_project(
            project_id="owned-by-reviewer",
            idea="Second project",
            owner_id=reviewer["user_id"],
        )

        self.auth.add_project_member(
            project_id=first["project_id"],
            email="reviewer@example.com",
            role="reviewer",
        )

        owner_ids = {
            project["project_id"]
            for project in self.projects.list_projects(
                user_id=owner["user_id"]
            )
        }
        reviewer_ids = {
            project["project_id"]
            for project in self.projects.list_projects(
                user_id=reviewer["user_id"]
            )
        }
        stranger_ids = {
            project["project_id"]
            for project in self.projects.list_projects(
                user_id=stranger["user_id"]
            )
        }
        admin_ids = {
            project["project_id"]
            for project in self.projects.list_projects(
                user_id="admin-id",
                is_admin=True,
            )
        }

        self.assertEqual(owner_ids, {"owned-by-owner"})
        self.assertEqual(reviewer_ids, {"owned-by-owner", "owned-by-reviewer"})
        self.assertEqual(stranger_ids, set())
        self.assertEqual(admin_ids, {"owned-by-owner", "owned-by-reviewer"})
        self.assertEqual(
            self.auth.get_project_role("owned-by-owner", reviewer),
            "reviewer",
        )

    def test_disabling_user_revokes_existing_sessions(self):
        user = self.auth.create_user(
            email="disabled@example.com",
            display_name="Disabled",
            password="disabled account password",
            role="viewer",
        )
        token, _ = self.auth.create_session(user["user_id"])
        updated = self.auth.update_user(user["user_id"], is_active=False)
        self.assertFalse(updated["is_active"])
        self.assertIsNone(self.auth.get_session_user(token))


if __name__ == "__main__":
    unittest.main()
