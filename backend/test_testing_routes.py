"""HTTP-level tests for the testing workspace and downloadable documents."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.agents.testing_agent.schemas import TestCase, TestSuite
from app.core.security import auth_store
from app.core.storage.project_store import project_store
from app.core.testing_store import test_store


class TestingRoutesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "specra-testing-routes.sqlite3"
        self.old_project_path = project_store.db_path
        self.old_auth_path = auth_store.db_path
        self.old_test_path = test_store.db_path

        project_store.db_path = self.db_path
        project_store._initialize_database()
        auth_store.db_path = self.db_path
        auth_store._initialize_database()
        test_store.db_path = self.db_path
        test_store._initialize_database()

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
                "display_name": "Specra Admin",
                "password": "admin-password-long",
            },
        )
        self.assertEqual(bootstrap.status_code, 201, bootstrap.text)
        project_response = self.client.post(
            "/api/v1/projects",
            json={"idea": "A shop where customers can search and save items."},
        )
        self.assertEqual(project_response.status_code, 201, project_response.text)
        self.project_id = project_response.json()["project_id"]

        project_store.save_artifact(
            self.project_id,
            "requirements",
            {
                "project_name": "Shop Demo",
                "objective": "Customers can discover items.",
                "functional_requirements": [
                    "Customers can search for items.",
                    "Customers can save items to a list.",
                ],
                "non_functional_requirements": ["Search should be usable on mobile."],
                "user_roles": ["Customer"],
                "constraints": [],
                "assumptions": [],
                "risks": [],
                "clarifications_needed": [],
            },
        )
        project_store.save_artifact(
            self.project_id,
            "project_plan",
            {
                "milestones": [{
                    "name": "Search",
                    "description": "Implement search.",
                    "requirement_refs": ["FR-001"],
                    "tasks": [],
                }],
            },
        )
        project_store.save_artifact(
            self.project_id,
            "architecture",
            {
                "architecture_style": "Layered",
                "frontend": "React",
                "backend": "FastAPI",
                "database": "SQLite",
                "components": [{
                    "name": "Search",
                    "responsibility": "Search items.",
                    "related_requirements": ["FR-001"],
                }],
                "api_endpoints": [],
                "data_flow": [],
                "external_integrations": [],
                "architectural_assumptions": [],
                "architecture_decisions": [],
            },
        )

    def tearDown(self):
        self.client.close()
        self.env_patch.stop()
        project_store.db_path = self.old_project_path
        auth_store.db_path = self.old_auth_path
        test_store.db_path = self.old_test_path
        self.temp.cleanup()

    @staticmethod
    def fake_suite():
        return TestSuite(
            project_name="Shop Demo",
            summary="The generated test suite covers search and saved items.",
            cases=[
                TestCase(
                    test_id="TC-001",
                    requirement_id="FR-001",
                    requirement_text="Customers can search for items.",
                    title="Search returns matching items",
                    test_type="acceptance",
                    priority="P1",
                    objective="Verify the search filters the item catalogue.",
                    preconditions=["The item catalogue contains a known item."],
                    steps=["Enter the known item's name.", "Submit the search."],
                    expected_result="Matching items are returned.",
                    generation_source="llm",
                    status="not_run",
                )
            ],
            requirement_coverage=["FR-001"],
            coverage_warnings=["FR-002 needs further edge-case coverage."],
        )

    def test_generate_suite_and_download_documents(self):
        with patch(
            "app.api.routes.testing.TestingAgent.generate",
            return_value=self.fake_suite(),
        ):
            generated = self.client.post(
                f"/api/v1/projects/{self.project_id}/tests/generate"
            )
        self.assertEqual(generated.status_code, 201, generated.text)
        self.assertEqual(generated.json()["suite"]["suite_version"], 1)
        self.assertEqual(generated.json()["suite"]["cases"][0]["status"], "not_run")

        documents = [
            ("srs", "text/markdown", "Software Requirements Specification"),
            ("sdd", "text/markdown", "Software Design Description"),
            ("test-report", "text/markdown", "Test Report"),
            ("traceability", "text/csv", "requirement_id"),
        ]
        for document_type, media_substring, expected_text in documents:
            with self.subTest(document_type=document_type):
                response = self.client.get(
                    f"/api/v1/projects/{self.project_id}/documents/{document_type}" + ("" if document_type == "traceability" else "?format=md")
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIn(media_substring, response.headers["content-type"])
                self.assertIn("attachment;", response.headers.get("content-disposition", ""))
                self.assertIn(expected_text, response.text)

        report = self.client.get(
            f"/api/v1/projects/{self.project_id}/documents/test-report?format=md"
        )
        self.assertIn("Passed: 0", report.text)
        self.assertIn("Not run: 1", report.text)

    def test_pdf_and_powerpoint_document_exports(self):
        for document_type, expected_type, expected_extension, magic in [
            ("srs", "application/pdf", ".pdf", b"%PDF-"),
            (
                "sdd",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                ".pptx",
                b"PK",
            ),
        ]:
            with self.subTest(document_type=document_type):
                format_name = "pptx" if expected_extension == ".pptx" else "pdf"
                response = self.client.get(
                    f"/api/v1/projects/{self.project_id}/documents/{document_type}?format={format_name}"
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIn(expected_type, response.headers["content-type"])
                self.assertTrue(response.content.startswith(magic))
                self.assertIn(expected_extension, response.headers["content-disposition"])

    def test_only_authorized_testers_can_record_execution_status(self):
        with patch(
            "app.api.routes.testing.TestingAgent.generate",
            return_value=self.fake_suite(),
        ):
            generated = self.client.post(
                f"/api/v1/projects/{self.project_id}/tests/generate"
            )
        self.assertEqual(generated.status_code, 201)

        updated = self.client.patch(
            f"/api/v1/projects/{self.project_id}/tests/cases/TC-001/result",
            json={
                "status": "passed",
                "execution_notes": "Observed two matching items.",
                "environment": "test build abc123",
            },
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["suite"]["cases"][0]["status"], "passed")

        report = self.client.get(
            f"/api/v1/projects/{self.project_id}/documents/test-report"
        )
        self.assertIn("Passed: 1", report.text)
        self.assertIn("Cases marked as executed: 1", report.text)


if __name__ == "__main__":
    unittest.main()
