"""Tests for requirement-linked test generation, persistence, and exports."""
import csv
import tempfile
import unittest
from io import StringIO
from pathlib import Path

from app.agents.testing_agent.agent import TestingAgent
from app.agents.testing_agent.schemas import (
    TestCaseDraft,
    TestSuite,
    TestSuiteDraft,
)
from app.core.document_export import (
    render_sdd,
    render_srs,
    render_test_report,
    render_traceability_csv,
)
from app.core.storage.project_store import ProjectStore
from app.core.testing_store import TestStore


class FakeLLMClient:
    def generate_structured(self, system_prompt, user_prompt, output_schema):
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.output_schema = output_schema
        return TestSuiteDraft(
            project_name="Shop Demo",
            summary="Covers core purchase requirements with observable outcomes.",
            test_cases=[
                TestCaseDraft(
                    requirement_ref="FR-001",
                    title="Authenticated user adds an item to cart",
                    test_type="acceptance",
                    priority="P1",
                    objective="Verify an authenticated customer can add an available item.",
                    preconditions=["A customer account exists.", "At least one active item is available."],
                    steps=[
                        "Sign in as the customer.",
                        "Open an available item.",
                        "Choose Add to Cart.",
                        "Open the cart and inspect the item list.",
                    ],
                    expected_result="The selected item appears in the cart with the correct quantity.",
                ),
                TestCaseDraft(
                    requirement_ref="unrecognized requirement reference",
                    title="Invalid reference should be discarded",
                    test_type="negative",
                    priority="P2",
                    objective="Exercise the validation path.",
                    steps=["Attempt the proposed operation."],
                    expected_result="The operation is rejected.",
                ),
            ],
        )


class TestingAgentQualityTests(unittest.TestCase):
    def test_unknown_requirement_refs_are_reported_and_missing_coverage_is_filled(self):
        agent = TestingAgent(model_name="fake-model")
        fake_client = FakeLLMClient()
        agent.llm_client = fake_client

        suite = agent.generate(
            {
                "project_name": "Shop Demo",
                "objective": "A small store.",
                "functional_requirements": [
                    "Customers can add available items to their cart.",
                    "Customers can remove items from their cart.",
                ],
                "non_functional_requirements": ["The cart shall be usable on mobile screens."],
            },
            project_plan={"milestones": []},
            architecture={"components": []},
        )

        self.assertEqual(fake_client.output_schema, TestSuiteDraft)
        self.assertIn("FR-001", fake_client.user_prompt)
        self.assertIn("FR-002", fake_client.user_prompt)
        self.assertEqual(suite.requirement_coverage, ["FR-001", "FR-002"])
        self.assertEqual([case.test_id for case in suite.cases], ["TC-001", "TC-002"])
        self.assertEqual(suite.cases[0].generation_source, "llm")
        self.assertEqual(suite.cases[1].generation_source, "template_fallback")
        self.assertTrue(any("could not be resolved" in item for item in suite.coverage_warnings))
        self.assertTrue(any("FR-002" in item for item in suite.coverage_warnings))
        self.assertTrue(all(case.status == "not_run" for case in suite.cases))


class TestStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "testing.sqlite3"
        self.projects = ProjectStore(self.db_path)
        self.projects.create_project(
            project_id="project-one",
            idea="A store project",
            owner_id="owner-id",
        )
        self.store = TestStore(self.db_path)

    def tearDown(self):
        self.temp.cleanup()

    def make_suite(self):
        return {
            "project_name": "Shop Demo",
            "summary": "A traced suite.",
            "cases": [
                {
                    "test_id": "TC-001",
                    "requirement_id": "FR-001",
                    "requirement_text": "Customers can add items.",
                    "title": "Add an item",
                    "test_type": "acceptance",
                    "priority": "P1",
                    "objective": "Verify add to cart.",
                    "preconditions": ["An item exists."],
                    "steps": ["Sign in.", "Add the item.", "Open the cart."],
                    "expected_result": "The item is visible in the cart.",
                    "generation_source": "llm",
                    "status": "not_run",
                }
            ],
            "requirement_coverage": ["FR-001"],
            "coverage_warnings": [],
        }

    def test_suites_are_versioned_and_results_are_not_fabricated(self):
        first = self.store.save_suite(
            project_id="project-one",
            suite=self.make_suite(),
            generation_model="test-model",
        )
        self.assertIsNotNone(first)
        self.assertEqual(first["suite_version"], 1)
        self.assertEqual(first["cases"][0]["status"], "not_run")
        self.assertIsNone(first["cases"][0]["executed_at"])

        passed = self.store.update_result(
            project_id="project-one",
            test_id="TC-001",
            status="passed",
            execution_notes="Observed expected cart contents.",
            environment="local test build 123",
            executed_by="tester@example.com",
        )
        self.assertEqual(passed["cases"][0]["status"], "passed")
        self.assertEqual(passed["cases"][0]["execution_notes"], "Observed expected cart contents.")
        self.assertEqual(passed["cases"][0]["executed_by"], "tester@example.com")
        self.assertIsNotNone(passed["cases"][0]["executed_at"])

        second = self.store.save_suite(
            project_id="project-one",
            suite=self.make_suite(),
            generation_model="test-model-2",
        )
        self.assertEqual(second["suite_version"], 2)
        self.assertEqual(second["cases"][0]["status"], "not_run")
        self.assertEqual(len(self.store.list_history("project-one")), 2)

    def test_unknown_case_and_invalid_status_are_rejected(self):
        self.store.save_suite(
            project_id="project-one",
            suite=self.make_suite(),
        )
        self.assertIsNone(self.store.update_result(
            project_id="project-one",
            test_id="TC-999",
            status="passed",
            execution_notes=None,
            environment=None,
            executed_by="tester@example.com",
        ))
        with self.assertRaisesRegex(ValueError, "Status must be one of"):
            self.store.update_result(
                project_id="project-one",
                test_id="TC-001",
                status="invented",
                execution_notes=None,
                environment=None,
                executed_by="tester@example.com",
            )


class DocumentExportTests(unittest.TestCase):
    def setUp(self):
        self.project = {
            "project_id": "project-123",
            "project_name": "Shop Demo",
            "idea": "A simple online store for books.",
        }
        self.artifacts = {
            "requirements": {
                "project_name": "Shop Demo",
                "objective": "Let customers discover and buy books.",
                "functional_requirements": [
                    "Customers can search books.",
                    "Customers can add books to a cart.",
                ],
                "non_functional_requirements": ["Search results should be accessible."],
                "user_roles": ["Customer", "Administrator"],
                "constraints": ["Keep the first version small."],
                "assumptions": ["A book catalogue is available."],
                "risks": ["Payment provider may be unavailable."],
                "clarifications_needed": ["Confirm supported payment methods."],
            },
            "project_plan": {
                "milestones": [
                    {
                        "name": "Search",
                        "description": "Implement book search.",
                        "requirement_refs": ["FR-001"],
                        "tasks": [{"description": "Build search endpoint.", "requirement_refs": ["FR-001"]}],
                    }
                ],
            },
            "architecture": {
                "architecture_style": "Layered web application",
                "frontend": "React",
                "backend": "FastAPI",
                "database": "PostgreSQL",
                "authentication": "Session login",
                "components": [
                    {"name": "Search UI", "responsibility": "Find books.", "related_requirements": ["FR-001"]}
                ],
                "api_endpoints": [
                    {"name": "GET /books", "purpose": "Search books.", "related_requirements": ["FR-001"]}
                ],
                "data_flow": ["Customer submits a query; API returns matching books."],
                "external_integrations": ["Payment provider"],
                "architectural_assumptions": ["Search can start with basic text matching."],
                "architecture_decisions": [
                    {"decision": "Use FastAPI.", "rationale": "Python API stack.", "related_requirements": ["FR-001"]}
                ],
            },
            "technical_review": {
                "requirement_coverage": [
                    {
                        "requirement_id": "FR-001",
                        "in_project_plan": True,
                        "in_architecture": True,
                    }
                ]
            },
        }
        self.versions = {
            "requirements": 1,
            "project_plan": 2,
            "architecture": 3,
            "technical_review": 1,
        }

    def test_srs_sdd_test_report_and_traceability_csv_are_honest(self):
        srs = render_srs(self.project, self.artifacts, self.versions)
        self.assertIn("Software Requirements Specification", srs)
        self.assertIn("FR-001", srs)
        self.assertIn("FR-002", srs)
        self.assertIn("Draft", srs)

        sdd = render_sdd(self.project, self.artifacts, self.versions)
        self.assertIn("Software Design Description", sdd)
        self.assertIn("Search UI", sdd)
        self.assertIn("FastAPI", sdd)

        report_without_suite = render_test_report(self.project, None)
        self.assertIn("No test suite has been generated", report_without_suite)
        self.assertIn("does not claim that generated tests passed", report_without_suite)

        suite = {
            "suite_version": 1,
            "project_name": "Shop Demo",
            "cases": [{
                "test_id": "TC-001",
                "requirement_id": "FR-001",
                "requirement_text": "Customers can search books.",
                "title": "Search returns matches",
                "test_type": "acceptance",
                "priority": "P1",
                "objective": "Check search.",
                "preconditions": [],
                "steps": ["Search books."],
                "expected_result": "Matching books appear.",
                "generation_source": "llm",
                "status": "passed",
                "executed_at": "2026-10-13T08:00:00+00:00",
                "executed_by": "tester@example.com",
                "environment": "local",
                "execution_notes": "Result confirmed.",
            }],
            "coverage_warnings": [],
        }
        report = render_test_report(self.project, suite)
        self.assertIn("Passed: 1", report)
        self.assertIn("Not run: 0", report)
        self.assertIn("tester@example.com", report)

        matrix = render_traceability_csv(self.project, self.artifacts, suite)
        parsed = list(csv.DictReader(StringIO(matrix)))
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["requirement_id"], "FR-001")
        self.assertEqual(parsed[0]["in_architecture"], "yes")
        self.assertEqual(parsed[0]["test_case_ids"], "TC-001")
        self.assertEqual(parsed[1]["test_results"], "no_test_cases")


if __name__ == "__main__":
    unittest.main()
