"""Code-generation safety, scaffolding, versioning, and export tests."""
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from app.agents.code_generator.quality import CodeGenerationQualityController
from app.agents.code_generator.schemas import CodeBundleDraft, GeneratedFileDraft
from app.core.code_bundle_store import CodeBundleStore
from app.core.security import AuthStore
from app.core.storage.project_store import ProjectStore


def draft(files, name="Book Finder"):
    return CodeBundleDraft(
        project_name=name,
        summary="A reviewable project starter for the book-search blueprint.",
        files=files,
        setup_notes=["Open in VS Code and inspect source."],
        test_notes=["Run pytest in the backend directory."],
    )


class CodeGenerationQualityTests(unittest.TestCase):
    def setUp(self):
        self.controller = CodeGenerationQualityController()

    def test_scaffold_adds_vs_code_configuration_and_never_claims_execution(self):
        bundle = self.controller.validate(
            draft([
                GeneratedFileDraft(
                    path="backend/app/routes/books.py",
                    purpose="Book search endpoint",
                    content=(
                        "from fastapi import APIRouter\n"
                        "router = APIRouter()\n"
                        "@router.get('/books')\n"
                        "def list_books():\n"
                        "    return []\n"
                    ),
                ),
            ])
        )
        by_path = {item.path: item for item in bundle.files}
        self.assertIn("backend/app/main.py", by_path)
        self.assertIn("frontend/package.json", by_path)
        self.assertIn(".vscode/launch.json", by_path)
        self.assertIn(".vscode/tasks.json", by_path)
        self.assertIn("backend/tests/test_health.py", by_path)
        self.assertEqual(bundle.execution_status, "not_executed")
        self.assertEqual(bundle.validation_status, "static_checks_clear")
        self.assertIn("not been run", by_path["SPECra_CODEGEN_GUIDE.md"].content.lower())

    def test_model_cannot_replace_trusted_vscode_tasks_or_health_test(self):
        bundle = self.controller.validate(
            draft([
                GeneratedFileDraft(
                    path=".vscode/tasks.json",
                    purpose="Attempted task override",
                    content='{"command": "printenv"}',
                ),
                GeneratedFileDraft(
                    path="backend/tests/test_health.py",
                    purpose="Attempted test override",
                    content="def test_health(): assert False",
                ),
                GeneratedFileDraft(
                    path="backend/app/main.py",
                    purpose="Custom API entry point",
                    content="from fastapi import FastAPI\\napp = FastAPI()\\n",
                ),
            ])
        )
        by_path = {item.path: item for item in bundle.files}
        task_config = json.loads(by_path[".vscode/tasks.json"].content)
        self.assertNotIn("printenv", by_path[".vscode/tasks.json"].content)
        self.assertIn("pytest", by_path[".vscode/tasks.json"].content)
        self.assertIn("from fastapi.testclient import TestClient", by_path["backend/tests/test_health.py"].content)
        self.assertIn('/health', by_path["backend/app/main.py"].content)
        self.assertTrue(any("deterministic /health endpoint" in note for note in bundle.validation_warnings))

    def test_project_name_is_escaped_in_html_scaffold(self):
        unsafe_name = "<script>alert(1)</script>"
        bundle = self.controller.validate(draft([], name=unsafe_name))
        by_path = {item.path: item for item in bundle.files}
        html = by_path["frontend/index.html"].content
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("projectTitle = ", by_path["frontend/src/App.jsx"].content)

    def test_invalid_json_manifest_is_replaced_with_safe_scaffold(self):
        bundle = self.controller.validate(
            draft([
                GeneratedFileDraft(
                    path="frontend/package.json",
                    purpose="Broken manifest",
                    content="{not valid json",
                ),
            ])
        )
        manifest = next(item for item in bundle.files if item.path == "frontend/package.json")
        json.loads(manifest.content)
        self.assertTrue(any("replaced" in note for note in bundle.validation_warnings))
        self.assertEqual(bundle.validation_status, "needs_review")

    def test_path_traversal_credentials_and_script_files_are_rejected(self):
        bad_inputs = [
            ("../../outside.py", "print('no')"),
            (".env", "SECRET=value"),
            ("scripts/postinstall.sh", "rm -rf /"),
            ("backend/app/../../../outside.py", "print('no')"),
        ]
        for path, body in bad_inputs:
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    self.controller.validate(draft([
                        GeneratedFileDraft(
                            path=path,
                            purpose="Unsafe path",
                            content=body,
                        )
                    ]))

    def test_secret_shaped_tokens_are_not_saved(self):
        with self.assertRaisesRegex(ValueError, "credential or private key"):
            self.controller.validate(draft([
                GeneratedFileDraft(
                    path="backend/app/settings.py",
                    purpose="Unsafe credential example",
                    content='API_KEY = "sk-123456789012345678901234567890"',
                )
            ]))

    def test_duplicate_paths_and_invalid_fastapi_entrypoint_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.controller.validate(draft([
                GeneratedFileDraft(path="backend/app/routes.py", purpose="One", content="x = 1"),
                GeneratedFileDraft(path="backend/app/ROUTES.py", purpose="Two", content="x = 2"),
            ]))
        with self.assertRaisesRegex(ValueError, "syntax error"):
            self.controller.validate(draft([
                GeneratedFileDraft(
                    path="backend/app/main.py",
                    purpose="Invalid entry point",
                    content="def app(:",
                )
            ]))


class CodeBundleStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "code-bundles.sqlite3"
        self.projects = ProjectStore(self.db_path)
        self.auth = AuthStore(self.db_path)
        self.user = self.auth.create_user(
            email="developer@example.com",
            display_name="Developer",
            password="developer-password-long",
            role="developer",
        )
        self.projects.create_project(
            project_id="code-project",
            idea="A small book-finder app.",
            owner_id=self.user["user_id"],
        )
        self.store = CodeBundleStore(self.db_path)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def make_bundle(version_note):
        return {
            "project_name": "Book Finder",
            "summary": version_note,
            "stack": "fastapi-react",
            "files": [
                {
                    "path": "backend/app/main.py",
                    "purpose": "API entry point",
                    "content": 'from fastapi import FastAPI\napp = FastAPI()\n',
                }
            ],
            "setup_notes": [],
            "test_notes": [],
            "validation_warnings": [],
            "validation_status": "static_checks_clear",
            "execution_status": "not_executed",
            "generation_source": "llm_plus_scaffold",
        }

    def test_bundle_versions_are_separate_and_history_is_listable(self):
        first = self.store.save_bundle(
            project_id="code-project",
            created_by=self.user["user_id"],
            bundle=self.make_bundle("First draft"),
            generation_model="test-model",
        )
        second = self.store.save_bundle(
            project_id="code-project",
            created_by=self.user["user_id"],
            bundle=self.make_bundle("Second draft"),
            generation_model="test-model-2",
        )
        self.assertEqual(first["bundle_version"], 1)
        self.assertEqual(second["bundle_version"], 2)
        self.assertEqual(self.store.get_latest_bundle("code-project")["summary"], "Second draft")
        self.assertEqual(len(self.store.list_bundles("code-project")), 2)


if __name__ == "__main__":
    unittest.main()
