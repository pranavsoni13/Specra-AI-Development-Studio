"""Validate generated source paths and add a deterministic VS Code scaffold.

Generated code is stored/exported as source; this module never executes it.
"""
from __future__ import annotations

import ast
import json
import re
from html import escape
from pathlib import PurePosixPath

from .schemas import CodeBundle, CodeBundleDraft, CodeFile


MAX_FILES = 45
MAX_TOTAL_CHARS = 500_000
MAX_FILE_CHARS = 30_000
ALLOWED_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".html", ".css",
    ".md", ".txt", ".toml", ".yaml", ".yml", ".xml", ".svg",
}
ALLOWED_EXTENSIONLESS = {"dockerfile", "makefile"}
RESERVED_PATHS = {
    ".gitignore",
    ".editorconfig",
    ".env.example",
    ".vscode/launch.json",
    ".vscode/tasks.json",
    "specra_codegen_guide.md",
    "backend/tests/test_health.py",
}
SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b"),
    re.compile(r"\bxai-[A-Za-z0-9_-]{20,}\b", re.IGNORECASE),
    re.compile(r"\bor-v1-[A-Za-z0-9_-]{24,}\b", re.IGNORECASE),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return slug[:48] or "specra-project"


def _file(path: str, purpose: str, content: str) -> CodeFile:
    return CodeFile(path=path, purpose=purpose, content=content)


def deterministic_scaffold(project_name: str) -> list[CodeFile]:
    """Files in this function are trusted scaffolding, never LLM-supplied IDE commands."""
    title = json.dumps(project_name.strip() or "Specra Generated Project")
    html_title = escape(project_name.strip() or "Specra Generated Project", quote=True)
    slug = _slug(project_name)
    files = [
        _file(
            "backend/app/main.py",
            "Deterministic FastAPI entry point used if the model omits one.",
            f'''"""FastAPI starter entry point for {project_name}."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title={title})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {{"status": "healthy"}}


@app.get("/api/v1/info")
def project_info():
    return {{
        "project": {title},
        "message": "Starter API is running. Implement approved project behavior in this codebase.",
    }}
''',
        ),
        _file(
            "backend/app/__init__.py",
            "Python package marker.",
            '"""Generated project backend package."""\n',
        ),
        _file(
            "backend/requirements.txt",
            "Minimal backend and testing dependencies for the starter scaffold.",
            "fastapi>=0.115,<1.0\nuvicorn[standard]>=0.30,<1.0\npytest>=8,<9\nhttpx>=0.27,<1.0\n",
        ),
        _file(
            "backend/tests/test_health.py",
            "Smoke test for the deterministic FastAPI health endpoint.",
            '''from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_healthy_status():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
''',
        ),
        _file(
            "frontend/package.json",
            "Minimal React/Vite scripts and dependencies.",
            json.dumps(
                {
                    "name": slug,
                    "private": True,
                    "version": "0.1.0",
                    "type": "module",
                    "scripts": {
                        "dev": "vite",
                        "build": "vite build",
                        "preview": "vite preview",
                    },
                    "dependencies": {
                        "@vitejs/plugin-react": "latest",
                        "vite": "latest",
                        "react": "latest",
                        "react-dom": "latest",
                    },
                    "devDependencies": {},
                },
                indent=2,
            ) + "\n",
        ),
        _file(
            "frontend/index.html",
            "Vite document entry point.",
            f'''<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content="{html_title} starter application" />
    <title>{html_title}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
''',
        ),
        _file(
            "frontend/vite.config.js",
            "Vite development server and local FastAPI proxy.",
            '''import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
});
''',
        ),
        _file(
            "frontend/src/main.jsx",
            "React entry point used if the model omits one.",
            '''import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
''',
        ),
        _file(
            "frontend/src/App.jsx",
            "Minimal status dashboard used if the model omits one.",
            f'''import {{ useEffect, useState }} from "react";

const projectTitle = {title};

export default function App() {{
  const [health, setHealth] = useState("checking");

  useEffect(() => {{
    fetch("/health")
      .then((response) => {{
        if (!response.ok) throw new Error("Backend is not healthy");
        return response.json();
      }})
      .then((data) => setHealth(data.status || "available"))
      .catch(() => setHealth("offline"));
  }}, []);

  return (
    <main className="page-shell">
      <section className="hero-panel">
        <span className="eyebrow">GENERATED STARTER PROJECT</span>
        <h1>{{projectTitle}}</h1>
        <p>
          The starter frontend is connected to the local FastAPI health endpoint.
          Continue implementing the approved requirements in the generated modules.
        </p>
        <div className="status-row">
          <span className={`status-dot status-${health}`} />
          <span>Backend status: <strong>{health}</strong></span>
        </div>
      </section>
    </main>
  );
}}
''',
        ),
        _file(
            "frontend/src/styles.css",
            "Responsive base styling for the default dashboard.",
            '''* { box-sizing: border-box; }
:root {
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #eef2ff;
  background: #080c14;
  font-synthesis: none;
  text-rendering: optimizeLegibility;
}
body { margin: 0; min-width: 320px; min-height: 100vh; }
button, input, select, textarea { font: inherit; }
.page-shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 28px;
  background: radial-gradient(circle at 18% 12%, #243154 0, transparent 38%), #080c14;
}
.hero-panel {
  width: min(100%, 760px);
  padding: clamp(26px, 5vw, 54px);
  border: 1px solid #29334b;
  border-radius: 22px;
  background: rgba(15, 22, 38, .94);
  box-shadow: 0 30px 100px rgba(0, 0, 0, .35);
}
.eyebrow {
  color: #9bafff;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: .16em;
}
h1 { margin: 14px 0; font-size: clamp(28px, 5vw, 46px); letter-spacing: -.05em; }
.hero-panel p { color: #aab6cf; font-size: 14px; line-height: 1.8; }
.status-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 22px;
  padding: 13px 15px;
  border: 1px solid #29334b;
  border-radius: 12px;
  color: #bac5de;
  font-size: 12px;
}
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: #d5b66b; }
.status-healthy, .status-available { background: #68d4a1; }
.status-offline { background: #ed7983; }
''',
        ),
        _file(
            ".vscode/launch.json",
            "Trusted VS Code debug configuration for FastAPI.",
            '''{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Specra Project: FastAPI",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"],
      "cwd": "${workspaceFolder}/backend",
      "envFile": "${workspaceFolder}/backend/.env"
    }
  ]
}
''',
        ),
        _file(
            ".vscode/tasks.json",
            "Trusted VS Code tasks for install, run, test, and build commands.",
            '''{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Backend: Install dependencies",
      "type": "shell",
      "command": "python -m pip install -r requirements.txt",
      "options": { "cwd": "${workspaceFolder}/backend" },
      "problemMatcher": []
    },
    {
      "label": "Backend: Run API",
      "type": "shell",
      "command": "python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000",
      "options": { "cwd": "${workspaceFolder}/backend" },
      "isBackground": true,
      "problemMatcher": []
    },
    {
      "label": "Backend: Run tests",
      "type": "shell",
      "command": "python -m pytest",
      "options": { "cwd": "${workspaceFolder}/backend" },
      "problemMatcher": []
    },
    {
      "label": "Frontend: Install dependencies",
      "type": "shell",
      "command": "npm install",
      "options": { "cwd": "${workspaceFolder}/frontend" },
      "problemMatcher": []
    },
    {
      "label": "Frontend: Start Vite",
      "type": "shell",
      "command": "npm run dev",
      "options": { "cwd": "${workspaceFolder}/frontend" },
      "isBackground": true,
      "problemMatcher": []
    },
    {
      "label": "Frontend: Build",
      "type": "shell",
      "command": "npm run build",
      "options": { "cwd": "${workspaceFolder}/frontend" },
      "problemMatcher": []
    }
  ]
}
''',
        ),
        _file(
            ".editorconfig",
            "Consistent source-file formatting defaults.",
            "root = true\n\n[*]\ncharset = utf-8\nend_of_line = lf\ninsert_final_newline = true\nindent_style = space\nindent_size = 2\n\n[*.py]\nindent_size = 4\n",
        ),
        _file(
            ".gitignore",
            "Ignores local secrets, caches, and build artefacts.",
            '''.env
.env.*
!.env.example
.venv/
venv/
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
coverage/
node_modules/
dist/
*.sqlite
*.sqlite3
*.db
''',
        ),
        _file(
            ".env.example",
            "Placeholder environment file; contains no credentials.",
            "APP_ENV=development\n# Add required project variables as placeholders only.\n",
        ),
        _file(
            "SPECra_CODEGEN_GUIDE.md",
            "Honest setup and VS Code testing guide.",
            f'''# {project_name} — VS Code setup

This is an AI-generated starter bundle. It has **not** been automatically executed or verified end-to-end by Specra. Review the source before running it.

## Open in Visual Studio Code

1. Extract the downloaded ZIP to a new folder.
2. Open that folder in Visual Studio Code.
3. Review the generated files and `backend/requirements.txt` / `frontend/package.json` before installing dependencies.
4. Open the Extensions view and install the Python and Python Debugger extensions if prompted.

## Backend

From the `backend` folder, create a virtual environment and install dependencies:

```bash
python -m venv .venv
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API health endpoint: `http://127.0.0.1:8000/health`.

## Frontend

From the `frontend` folder:

```bash
npm install
npm run dev
```

Use the URL printed by Vite. Its development server proxies `/api` and `/health` to the backend at `127.0.0.1:8000`.

## VS Code tasks

Use **Terminal → Run Task** to install dependencies, run the API, run backend pytest tests, start Vite, or build the frontend. The included `.vscode` tasks are deterministic Specra scaffolding, not generated shell scripts.

## Result honesty

The backend smoke-test source is a real test file, but it has not been run on this machine. Code generation and test-case generation are not proof that the project meets every requirement. Run tests and frontend build, inspect failures, and review the security of generated source before deployment. Add project-specific tests from Specra's Testing workspace where requirements need them.
''',
        ),
    ]
    return files


class CodeGenerationQualityController:
    def validate(self, draft: CodeBundleDraft) -> CodeBundle:
        raw_files = list(draft.files)
        if len(raw_files) > 35:
            raise ValueError("The generated project contains more than 35 model-authored files.")

        validated: dict[str, CodeFile] = {}
        warnings: list[str] = []
        total_chars = 0

        for item in raw_files:
            raw_path = item.path.strip()
            if not raw_path or "\\" in raw_path or "\x00" in raw_path:
                raise ValueError("A generated file has an invalid path.")
            if raw_path.startswith("/") or re.match(r"^[A-Za-z]:", raw_path):
                raise ValueError("Absolute paths are not allowed in generated bundles.")
            path = PurePosixPath(raw_path)
            parts = path.parts
            if not parts or any(part in {"", ".", ".."} for part in parts):
                raise ValueError("Generated file paths must not contain traversal segments.")
            lowered_parts = {part.casefold() for part in parts}
            if ".git" in lowered_parts or ".ssh" in lowered_parts:
                raise ValueError("Version-control internals and SSH folders are not allowed.")
            if any(part.startswith(".env") for part in parts[:-1]):
                raise ValueError("Environment/secret folders are not allowed.")
            filename = parts[-1].casefold()
            if filename in {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519"}:
                raise ValueError("Credential files are not allowed in generated bundles.")
            if ".github" in lowered_parts and "workflows" in lowered_parts:
                raise ValueError("Generated CI workflows are disabled until code execution is sandboxed.")
            suffix = path.suffix.casefold()
            if suffix in {".sh", ".bash", ".bat", ".cmd", ".ps1", ".pem", ".key", ".p12", ".pfx", ".exe", ".dll", ".so", ".bin", ".sqlite", ".sqlite3", ".db"}:
                raise ValueError(f"Files with the '{suffix}' extension are not allowed in generated bundles.")
            if suffix and suffix not in ALLOWED_SUFFIXES:
                raise ValueError(f"Unsupported generated file type: {suffix}")
            if not suffix and filename not in ALLOWED_EXTENSIONLESS and filename not in {"license", "notice"}:
                raise ValueError(f"Unsupported extensionless generated file: {filename}")

            canonical_path = path.as_posix()
            casefold_path = canonical_path.casefold()
            if casefold_path in RESERVED_PATHS:
                warnings.append(
                    f"Model output for {canonical_path} was replaced by trusted Specra scaffolding."
                )
                continue
            if casefold_path in validated:
                raise ValueError(f"Duplicate generated file path: {canonical_path}")
            body = item.content
            if len(body) > MAX_FILE_CHARS:
                raise ValueError(f"Generated file exceeds {MAX_FILE_CHARS} characters: {canonical_path}")
            if any(pattern.search(body) for pattern in SECRET_PATTERNS):
                raise ValueError(
                    f"Generated file appears to contain a credential or private key: {canonical_path}. "
                    "Remove it from the model output and regenerate; Specra will not store it."
                )

            total_chars += len(body)
            if total_chars > MAX_TOTAL_CHARS:
                raise ValueError("Generated bundle exceeds the 500,000-character safety limit.")
            validated[casefold_path] = _file(
                canonical_path,
                item.purpose.strip() or "Generated source file",
                body,
            )

        if len(validated) > MAX_FILES:
            raise ValueError("Generated bundle exceeds the 45-file safety limit.")

        # Reserve IDE configs, secret examples and minimal entry points for
        # deterministic scaffolding. The model cannot control VS Code commands.
        scaffold = deterministic_scaffold(draft.project_name)
        scaffold_map = {file.path.casefold(): file for file in scaffold}
        for reserved in RESERVED_PATHS:
            validated.pop(reserved, None)

        for key, fallback in scaffold_map.items():
            if key not in validated:
                validated[key] = fallback

        # Repair an invalid package manifest with a deterministic known-good scaffold.
        package_key = "frontend/package.json"
        package = validated.get(package_key)
        try:
            json.loads(package.content if package else "{}")
        except json.JSONDecodeError:
            validated[package_key] = scaffold_map[package_key]
            warnings.append(
                "The generated frontend/package.json was invalid JSON and was replaced by a minimal Vite/React manifest."
            )

        # Keep the backend startup probe independent of model output, so a
        # downloaded bundle has a deterministic /health endpoint to test.
        main_key = "backend/app/main.py"
        main_file = validated.get(main_key)
        if main_file and "/health" not in main_file.content:
            validated[main_key] = _file(
                main_file.path,
                main_file.purpose + " Includes the deterministic Specra health endpoint.",
                main_file.content.rstrip()
                + '\\n\\n@app.get("/health")\\ndef health_check():\\n    return {"status": "healthy"}\\n',
            )
            warnings.append(
                "Added a deterministic /health endpoint for the included VS Code smoke test."
            )

        # The generated test smoke check is deterministic; report syntax problems,
        # but never execute untrusted generated code inside the API process.
        for key, file in validated.items():
            if key.endswith(".py"):
                try:
                    ast.parse(file.content, filename=file.path)
                except SyntaxError as exc:
                    if key == "backend/app/main.py":
                        raise ValueError(
                            "The generated FastAPI entry point has a Python syntax error. "
                            "Regenerate the bundle before downloading it."
                        ) from exc
                    warnings.append(
                        f"Python syntax needs review in {file.path} (line {exc.lineno or 'unknown'})."
                    )
            if key.endswith(".json"):
                try:
                    json.loads(file.content)
                except json.JSONDecodeError:
                    if key == "frontend/package.json":
                        continue
                    warnings.append(f"JSON syntax needs review in {file.path}.")

        files = [validated[key] for key in sorted(validated)]
        if len(files) > MAX_FILES:
            raise ValueError("The final bundle exceeds the 45-file safety limit.")

        return CodeBundle(
            project_name=draft.project_name.strip(),
            summary=draft.summary.strip(),
            stack="fastapi-react",
            files=files,
            setup_notes=draft.setup_notes,
            test_notes=draft.test_notes,
            validation_warnings=warnings,
            validation_status="needs_review" if warnings else "static_checks_clear",
            execution_status="not_executed",
            generation_source="llm_plus_scaffold",
        )
