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
            summary="A real book catalogue search and reading-list application.",
            stack="fastapi-react",
            files=[
                CodeFile(
                    path="backend/app/main.py",
                    purpose="FastAPI entry point with the catalogue API registered",
                    content=(
                        "from fastapi import FastAPI\n"
                        "from app.routes.catalogue import router as catalogue_router\n"
                        "app = FastAPI(title='Book Finder')\n"
                        "app.include_router(catalogue_router, prefix='/api')\n"
                        "@app.get('/health')\n"
                        "def health(): return {'status': 'healthy'}\n"
                    ),
                ),
                CodeFile(
                    path="backend/app/routes/catalogue.py",
                    purpose="Search books and save them to a reader's list",
                    content=(
                        "from fastapi import APIRouter\n"
                        "router = APIRouter()\n"
                        "BOOKS = [{'id': 1, 'title': 'Dune'}]\n"
                        "@router.get('/books')\n"
                        "def search_books(q: str = ''):\n"
                        "    return [book for book in BOOKS if q.casefold() in book['title'].casefold()]\n"
                        "@router.post('/reading-list/{book_id}')\n"
                        "def save_book(book_id: int):\n"
                        "    return {'saved_book_id': book_id}\n"
                    ),
                ),
                CodeFile(
                    path="frontend/src/App.jsx",
                    purpose="Main application entry showing the book-search workflow",
                    content=(
                        "import BookSearch from './features/BookSearch.jsx';\n"
                        "export default function App() { return <BookSearch />; }\n"
                    ),
                ),
                CodeFile(
                    path="frontend/src/features/BookSearch.jsx",
                    purpose="Search the catalogue and add results to a reading list",
                    content=(
                        "import { useState } from 'react';\n"
                        "export default function BookSearch() {\n"
                        "  const [query, setQuery] = useState('');\n"
                        "  const [books, setBooks] = useState([]);\n"
                        "  const [error, setError] = useState('');\n"
                        "  async function search() {\n"
                        "    try {\n"
                        "      const response = await fetch('/api/books?q=' + encodeURIComponent(query));\n"
                        "      if (!response.ok) throw new Error('Search failed');\n"
                        "      setBooks(await response.json()); setError('');\n"
                        "    } catch (err) { setError(err.message); }\n"
                        "  }\n"
                        "  return <main><h1>Book Finder</h1><input value={query} onChange={e => setQuery(e.target.value)} />"
                        "<button onClick={search}>Search</button>{error && <p role='alert'>{error}</p>}"
                        "{books.map(book => <article key={book.id}>{book.title}</article>)}</main>;\n"
                        "}\n"
                    ),
                ),
            ],
            setup_notes=["Install backend and frontend dependencies."],
            test_notes=["Run pytest and npm run build before release."],
            validation_warnings=[],
            validation_status="static_checks_clear",
            execution_status="not_executed",
        )

    def test_list_code_bundles_reports_generation_readiness(self):
        response = self.client.get(
            f"/api/v1/projects/{self.project_id}/code-bundles"
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["can_generate"])
        self.assertTrue(payload["generation_ready"])
        self.assertIsNone(payload["generation_block_reason"])
        self.assertEqual(payload["my_role"], "admin")

    def test_list_code_bundles_explains_failed_technical_review(self):
        self._save_blueprint("FAIL")
        response = self.client.get(
            f"/api/v1/projects/{self.project_id}/code-bundles"
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["can_generate"])
        self.assertFalse(payload["generation_ready"])
        self.assertIn("technical review has not passed", payload["generation_block_reason"])

    def test_provider_failure_returns_actionable_code_generation_error(self):
        with patch(
            "app.api.routes.code_generation.CodeGenerationAgent"
        ) as agent_class:
            agent = agent_class.return_value
            agent.model_name = "qwen3-coder:480b-cloud"
            agent.generate.side_effect = RuntimeError("provider unavailable")
            response = self.client.post(
                f"/api/v1/projects/{self.project_id}/code-bundles/generate",
                json={"stack": "fastapi-react"},
            )
        self.assertEqual(response.status_code, 502, response.text)
        detail = response.json()["detail"]
        self.assertIn("ollama provider", detail)
        self.assertIn("qwen3-coder:480b-cloud", detail)
        self.assertIn("No files were saved", detail)
        self.assertIn("backend deployment logs", detail)

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
        generated_paths = [item["path"] for item in bundle["files"]]
        self.assertIn("backend/app/main.py", generated_paths)
        self.assertIn("backend/app/routes/catalogue.py", generated_paths)
        self.assertIn("frontend/src/App.jsx", generated_paths)
        self.assertIn("frontend/src/features/BookSearch.jsx", generated_paths)

        downloaded = self.client.get(
            f"/api/v1/projects/{self.project_id}/code-bundles/{bundle['bundle_id']}/download"
        )
        self.assertEqual(downloaded.status_code, 200, downloaded.text)
        self.assertIn("application/zip", downloaded.headers["content-type"])
        with ZipFile(BytesIO(downloaded.content)) as archive:
            self.assertIn("backend/app/main.py", archive.namelist())
            self.assertIn("backend/app/routes/catalogue.py", archive.namelist())
            self.assertIn("frontend/src/App.jsx", archive.namelist())
            self.assertIn("frontend/src/features/BookSearch.jsx", archive.namelist())
            self.assertNotIn("../outside.py", archive.namelist())

        detail = self.client.get(
            f"/api/v1/projects/{self.project_id}/code-bundles/{bundle['bundle_id']}"
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.json()["bundle"]["files"]), 4)

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
