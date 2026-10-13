"""HTTP tests for gated code generation and VS Code ZIP downloads."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app
from app.agents.code_generator.schemas import CodeBundle, CodeFile
from app.core.code_bundle_store import code_bundle_store
from app.core.copilot_store import copilot_store
from app.core.security import auth_store
from app.core.storage.project_store import project_store
from app.core.testing_store import test_store


class CodeGenerationRoutesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "code-routes.sqlite3"
        self.stores = [
            project_store,
            auth_store,
            test_store,
            copilot_store,
            code_bundle_store,
        ]
        self.old_paths = [store.db_path for store in self.stores]
        for store in self.stores:
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

        created = self.client.post(
            "/api/v1/projects",
            json={"idea": "A website where users can search and save books."},
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.project_id = created.json()["project_id"]
        self._save_blueprint("PASS")

    def tearDown(self):
        self.client.close()
        self.env_patch.stop()
        for store, old_path in zip(self.stores, self.old_paths):
            store.db_path = old_path
        self.temp.cleanup()

    def _save_blueprint(self, review_status):
        project_store.save_artifact(
            self.project_id,
            "requirements",
            {
                "project_name": "Book Finder",
                "objective": "Search a book catalogue.",
                "functional_requirements": [
                    "Users can search the book catalogue.",
                    "Users can save a book to a reading list.",
                ],
                "non_functional_requirements": [],
                "user_roles": ["Reader"],
                "constraints": [],
                "assumptions": [],
                "risks": [],
                "clarifications_needed": [],
            },
        )
        project_store.save_artifact(
            self.project_id,
            "project_plan",
            {"milestones": [{"name": "Search", "description": "Implement search.", "tasks": []}]},
        )
        project_store.save_artifact(
            self.project_id,
            "architecture",
            {
                "architecture_style": "Layered",
                "frontend": "React",
                "backend": "FastAPI",
                "database": "SQLite",
                "components": [],
                "api_endpoints": [],
                "data_flow": [],
                "external_integrations": [],
                "architectural_assumptions": [],
                "architecture_decisions": [],
            },
        )
        project_store.save_artifact(
            self.project_id,
            "technical_review",
            {
                "overall_status": review_status,
                "findings": [],
                "requirement_coverage": [],
            },
        )

    @staticmethod
    def fake_bundle(**kwargs):
        return CodeBundle(
            project_name="Book Finder",
            summary="A starter frontend and API for searching books.",
            stack="fastapi-react",
            files=[
                CodeFile(
                    path="backend/app/main.py",
                    purpose="API entry point",
                    content='from fastapi import FastAPI\napp = FastAPI()\n',
                ),
                CodeFile(
                    path="frontend/src/App.jsx",
                    purpose="Book search UI",
                    content="export default function App() { return <main>Books</main>; }",
                ),
            ],
            setup_notes=["Open the folder in Visual Studio Code."],
            test_notes=["Run pytest before making a release."],
            validation_warnings=[],
            validation_status="static_checks_clear",
            execution_status="not_executed",
        )

    def test_generate_version_and_download_safe_zip(self):
        with patch(
            "app.api.routes.code_generation.CodeGenerationAgent.generate",
            new=lambda agent, **kwargs: self.fake_bundle(**kwargs),
        ):
            response = self.client.post(
                f"/api/v1/projects/{self.project_id}/code-bundles/generate",
                json={"stack": "fastapi-react"},
            )
        self.assertEqual(response.status_code, 201, response.text)
        bundle = response.json()["bundle"]
        self.assertEqual(bundle["bundle_version"], 1)
        self.assertEqual(bundle["execution_status"], "not_executed")
        self.assertIn("backend/app/main.py", [item["path"] for item in bundle["files"]])

        downloaded = self.client.get(
            f"/api/v1/projects/{self.project_id}/code-bundles/{bundle['bundle_id']}/download"
        )
        self.assertEqual(downloaded.status_code, 200, downloaded.text)
        self.assertIn("application/zip", downloaded.headers["content-type"])
        with ZipFile(BytesIO(downloaded.content)) as archive:
            self.assertIn("backend/app/main.py", archive.namelist())
            self.assertIn("frontend/src/App.jsx", archive.namelist())
            self.assertNotIn("../outside.py", archive.namelist())

        detail = self.client.get(
            f"/api/v1/projects/{self.project_id}/code-bundles/{bundle['bundle_id']}"
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.json()["bundle"]["files"]), 2)

    def test_generation_requires_passed_technical_review(self):
        self._save_blueprint("FAIL")
        with patch(
            "app.api.routes.code_generation.CodeGenerationAgent.generate",
            new=lambda agent, **kwargs: self.fake_bundle(**kwargs),
        ):
            response = self.client.post(
                f"/api/v1/projects/{self.project_id}/code-bundles/generate",
                json={"stack": "fastapi-react"},
            )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("must pass", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
