"""HTTP tests for project Copilot authentication and private chat history."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.core.copilot_store import copilot_store
from app.core.security import auth_store
from app.core.storage.project_store import project_store
from app.core.testing_store import test_store


class CopilotRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "copilot-routes.sqlite3"
        self.paths = {
            "project": project_store.db_path,
            "auth": auth_store.db_path,
            "test": test_store.db_path,
            "copilot": copilot_store.db_path,
        }
        for store in (project_store, auth_store, test_store, copilot_store):
            store.db_path = self.db_path
            store._initialize_database()

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
        bootstrap = self.client.post(
            "/api/v1/auth/bootstrap",
            json={
                "bootstrap_token": "test-bootstrap-secret-not-real",
                "email": "admin@example.com",
                "display_name": "Admin",
                "password": "admin-password-long",
            },
        )
        self.assertEqual(bootstrap.status_code, 201, bootstrap.text)
        project = self.client.post(
            "/api/v1/projects",
            json={"idea": "Users can search a book catalogue."},
        )
        self.assertEqual(project.status_code, 201, project.text)
        self.project_id = project.json()["project_id"]

    def tearDown(self):
        self.client.close()
        self.env_patch.stop()
        for name, store in (
            ("project", project_store),
            ("auth", auth_store),
            ("test", test_store),
            ("copilot", copilot_store),
        ):
            store.db_path = self.paths[name]
        self.temp.cleanup()

    @staticmethod
    def fake_answer(**kwargs):
        return {
            "answer": "The project brief says users search a book catalogue.",
            "source_refs": [
                {
                    "source_id": "project-brief",
                    "title": "Project brief",
                    "kind": "project",
                }
            ],
            "proposed_changes": [],
            "model_name": "test-model",
        }

    def test_copilot_creates_private_project_conversations(self):
        anonymous_client = TestClient(app)
        anonymous = anonymous_client.get(
            f"/api/v1/projects/{self.project_id}/copilot"
        )
        anonymous_client.close()
        self.assertEqual(anonymous.status_code, 401)

        with patch(
            "app.api.routes.copilot.ProjectCopilotAgent.answer",
            new=self.fake_answer,
        ):
            first = self.client.post(
                f"/api/v1/projects/{self.project_id}/copilot/ask",
                json={"message": "Summarize the brief."},
            )
        self.assertEqual(first.status_code, 201, first.text)
        first_data = first.json()
        first_id = first_data["conversation"]["conversation_id"]
        self.assertEqual(len(first_data["conversation"]["messages"]), 2)
        self.assertEqual(first_data["answer"]["source_refs"][0]["source_id"], "project-brief")

        created_member = self.client.post(
            "/api/v1/auth/users",
            json={
                "email": "reviewer@example.com",
                "display_name": "Reviewer",
                "password": "reviewer-password-long",
                "role": "reviewer",
            },
        )
        self.assertEqual(created_member.status_code, 201, created_member.text)
        assigned = self.client.post(
            f"/api/v1/projects/{self.project_id}/members",
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

        listed = self.client.get(f"/api/v1/projects/{self.project_id}/copilot")
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(listed.json()["conversations"], [])

        hidden = self.client.get(
            f"/api/v1/projects/{self.project_id}/copilot/{first_id}"
        )
        self.assertEqual(hidden.status_code, 404)

        with patch(
            "app.api.routes.copilot.ProjectCopilotAgent.answer",
            new=self.fake_answer,
        ):
            second = self.client.post(
                f"/api/v1/projects/{self.project_id}/copilot/ask",
                json={"message": "What does the brief mean?"},
            )
        self.assertEqual(second.status_code, 201, second.text)
        self.assertNotEqual(
            second.json()["conversation"]["conversation_id"],
            first_id,
        )

    def test_viewer_can_read_project_but_cannot_spend_copilot_generation(self):
        self.client.post("/api/v1/auth/users", json={
            "email": "viewer@example.com",
            "display_name": "Viewer",
            "password": "viewer-password-long",
            "role": "viewer",
        })
        assigned = self.client.post(
            f"/api/v1/projects/{self.project_id}/members",
            json={"email": "viewer@example.com", "role": "viewer"},
        )
        self.assertEqual(assigned.status_code, 201, assigned.text)
        self.client.post("/api/v1/auth/logout")
        self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "viewer@example.com",
                "password": "viewer-password-long",
            },
        )

        readable = self.client.get(f"/api/v1/projects/{self.project_id}/copilot")
        self.assertEqual(readable.status_code, 200)
        self.assertFalse(readable.json()["can_ask"])

        denied = self.client.post(
            f"/api/v1/projects/{self.project_id}/copilot/ask",
            json={"message": "Use the language model now."},
        )
        self.assertEqual(denied.status_code, 403)


if __name__ == "__main__":
    unittest.main()
