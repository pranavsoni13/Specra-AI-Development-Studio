"""HTTP-level authentication and authorization tests.

These tests redirect the module-level SQLite stores to a temporary database,
so they never read or mutate a developer's normal project database.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.core.security import auth_store
from app.core.storage.project_store import project_store


class AuthRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous_project_path = project_store.db_path
        self.previous_auth_path = auth_store.db_path
        self.db_path = Path(self.temp.name) / "specra-http-test.sqlite3"

        project_store.db_path = self.db_path
        project_store._initialize_database()
        auth_store.db_path = self.db_path
        auth_store._initialize_database()

        self.env_patch = patch.dict(
            os.environ,
            {
                "AUTH_BOOTSTRAP_TOKEN": "test-bootstrap-secret-not-real",
                "AUTH_COOKIE_SECURE": "false",
            },
            clear=False,
        )
        self.env_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.env_patch.stop()
        project_store.db_path = self.previous_project_path
        auth_store.db_path = self.previous_auth_path
        self.temp.cleanup()

    def bootstrap_admin(self):
        response = self.client.post(
            "/api/v1/auth/bootstrap",
            json={
                "bootstrap_token": "test-bootstrap-secret-not-real",
                "email": "admin@example.com",
                "display_name": "Specra Admin",
                "password": "admin-password-long",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["user"]["role"], "admin")
        return response

    def test_project_api_rejects_anonymous_and_bootstrap_creates_admin(self):
        anonymous = self.client.get("/api/v1/projects")
        self.assertEqual(anonymous.status_code, 401)

        self.bootstrap_admin()
        current_user = self.client.get("/api/v1/auth/me")
        self.assertEqual(current_user.status_code, 200)
        self.assertEqual(current_user.json()["user"]["role"], "admin")

        created = self.client.post(
            "/api/v1/projects",
            json={"idea": "A small project for route authorization tests"},
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["status"], "created")

        listed = self.client.get("/api/v1/projects")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()), 1)

    def test_member_can_read_but_reviewer_cannot_run_or_change_context(self):
        self.bootstrap_admin()
        project = self.client.post(
            "/api/v1/projects",
            json={"idea": "A private project with a reviewer"},
        ).json()
        project_id = project["project_id"]

        created_user = self.client.post(
            "/api/v1/auth/users",
            json={
                "email": "reviewer@example.com",
                "display_name": "Project Reviewer",
                "password": "reviewer-password-long",
                "role": "reviewer",
            },
        )
        self.assertEqual(created_user.status_code, 201, created_user.text)

        assigned = self.client.post(
            f"/api/v1/projects/{project_id}/members",
            json={"email": "reviewer@example.com", "role": "reviewer"},
        )
        self.assertEqual(assigned.status_code, 201, assigned.text)

        self.client.post("/api/v1/auth/logout")
        login = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "reviewer@example.com",
                "password": "reviewer-password-long",
            },
        )
        self.assertEqual(login.status_code, 200, login.text)

        listed = self.client.get("/api/v1/projects")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([item["project_id"] for item in listed.json()], [project_id])

        project_read = self.client.get(f"/api/v1/projects/{project_id}")
        self.assertEqual(project_read.status_code, 200, project_read.text)

        cannot_run = self.client.post(f"/api/v1/projects/{project_id}/run")
        self.assertEqual(cannot_run.status_code, 403, cannot_run.text)

        cannot_add_context = self.client.post(
            f"/api/v1/projects/{project_id}/context",
            json={
                "name": "Unauthorized note",
                "kind": "note",
                "content": "This should not be stored by the reviewer.",
                "metadata": {},
            },
        )
        self.assertEqual(cannot_add_context.status_code, 403, cannot_add_context.text)

    def test_non_member_cannot_discover_project_by_id(self):
        self.bootstrap_admin()
        project = self.client.post(
            "/api/v1/projects",
            json={"idea": "A private project"},
        ).json()
        self.client.post("/api/v1/auth/users", json={
            "email": "stranger@example.com",
            "display_name": "Stranger",
            "password": "stranger-password-long",
            "role": "viewer",
        })
        self.client.post("/api/v1/auth/logout")
        self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "stranger@example.com",
                "password": "stranger-password-long",
            },
        )

        response = self.client.get(f"/api/v1/projects/{project['project_id']}")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
