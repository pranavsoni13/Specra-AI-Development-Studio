# Specra

**From idea to engineered reality.**

Specra is an AI-assisted software engineering studio that coordinates specialized agents to turn a product brief into traceable engineering artifacts. It is built as a full-stack web application with a React frontend and a FastAPI backend.

> Project status: the local agent workflow and selected deterministic contract tests have passed. A production deployment still requires a publicly reachable inference endpoint and deployment-ready persistence/configuration.

## Live demo

- **Web app:** <https://specra-ai-development-studio.vercel.app>
- **Backend health:** <https://specra-api-pranavsoni13.onrender.com/health>
- **Interactive API docs:** <https://specra-api-pranavsoni13.onrender.com/docs>

The frontend and backend are deployed separately. The health endpoint confirms backend availability; successful AI generation additionally depends on the configured Ollama API key, available model access, and remaining provider usage.

## What it does

- **Requirement analysis** — turns a project brief into structured functional requirements.
- **Project planning** — organizes requirements into milestones and tasks with requirement references.
- **Software architecture** — proposes an architecture, components, data flow, assumptions, and API endpoints.
- **Technical review** — checks requirement coverage, unsupported additions, and architectural consistency.
- **Project context** — stores and searches project-scoped source material.
- **Artifact lifecycle** — supports artifact review, refinement, version history, and restoration through the project API.
- **Traceability** — uses canonical requirement references (for example, `FR-001`) across generated artifacts.

## Technology stack

- **Frontend:** React, Vite
- **Backend:** Python, FastAPI, Uvicorn, Pydantic
- **Agent/model runtime:** Ollama Python client; Qwen models by default
- **Workflow and retrieval:** LangGraph, ChromaDB, sentence-transformers
- **Local persistence:** SQLite

## Repository layout

```text
Specra-AI-Development-Studio/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   ├── api/routes/
│   │   ├── core/
│   │   ├── rag/
│   │   └── workflows/
│   ├── requirements.txt
│   └── test_*.py
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.js
├── docs/                  # Architecture and deployment notes
├── knowledge/documents/   # Shared engineering reference corpus
├── scripts/               # Local developer utilities
├── render.yaml
└── README.md
```

Deterministic Python contract tests live in `backend/test_*.py` so they run with
the backend package on the Python import path. The runtime project workflow is
implemented in `backend/app/workflows/`; there are no separate root-level
workflow or memory modules.

## Run locally

### Prerequisites

- Python 3.10 or newer
- Node.js and npm
- Ollama installed and running
- Enough memory to run the selected local models

### 1. Start Ollama and download the default models

```bash
ollama pull qwen3:1.7b
ollama pull qwen3:4b
```

Keep Ollama running in a separate terminal. If `ollama serve` reports that port `11434` is already in use, an Ollama server may already be running; verify with `ollama list` rather than starting another server.

### 2. Start the backend

From the repository root:

```bash
cd backend
python -m venv .venv
```

Activate the environment, then install dependencies:

```bash
# Windows Command Prompt
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Backend endpoints:

- Health check: `http://127.0.0.1:8000/health`
- API documentation: `http://127.0.0.1:8000/docs`

### 3. Start the frontend

Open a second terminal at the repository root:

```bash
cd frontend
npm install
npm run dev
```

Vite serves the frontend at `http://localhost:5173` and proxies `/api` requests to the local backend at `http://127.0.0.1:8000` during development.

## Tests

Run deterministic contract tests from `backend/`:

```bash
python test_semantic_integrity.py
python test_refinement_flow.py
```

Run the full multi-agent workflow with:

```bash
python test_project_workflow.py
```

The full workflow invokes local language models and may take a long time on CPU-only hardware. It is not necessary to rerun it for routine documentation or frontend changes.

## Deployment notes

The frontend and backend are separate deployment concerns.

- The Vite proxy in `frontend/vite.config.js` applies to local development, not to a production deployment.
- The backend uses the Ollama Python client. A cloud-hosted backend cannot reach Ollama running only on a developer's computer. Configure a reachable Ollama-compatible endpoint with `OLLAMA_HOST` and, when required by the provider, `OLLAMA_API_KEY`. Configure the agent model names to match models available from that endpoint.
- The project currently uses SQLite for local project/context storage and ChromaDB for retrieval data. Ephemeral cloud filesystems can lose SQLite and generated vector-store files after restarts or redeployments. Use a persistent datastore/storage strategy before relying on long-term hosted data.
- Do not commit `.env` files, API keys, local databases, model weights, vector database runtime files, virtual environments, or build output.

## License

This project is distributed under the MIT License. See [LICENSE](LICENSE).


## Project memory and workspace restoration

- **Project Memory** stores project-scoped notes, constraints, design decisions,
  references, and code excerpts using the project-context API.
- The next **Run All Again** supplies up to eight saved sources (bounded to 12,000
  characters) as secondary context to requirement analysis. The current brief
  and explicit constraints take precedence over conflicting saved context.
- The browser remembers the last project, selected artifact, and scroll position.
  Browser storage cannot recover server-side records that have been lost.
- Render Free uses an ephemeral filesystem. Use durable database/storage before
  relying on projects surviving backend restarts and redeploys.
- Project-context vector indexing is opt-in with `ENABLE_PROJECT_CONTEXT_RAG=true`.
  It is disabled by default on low-memory hosting; saved text still works as
  context for the full workflow without a vector index.

## Blueprint Quality Lab

Run deterministic checks against the saved engineering blueprint to identify functional requirements missing from the plan, architecture components, or API capabilities; unresolved requirement references; open clarification questions; and technical review findings. The result is a **blueprint consistency report**, not proof that generated application code has been executed. Use the Testing Workspace to design test cases, record execution evidence, and export an honest Test Report. Code Studio produces a reviewable project bundle for download; untrusted generated code is not executed inside the Specra API server.

## Configurable LLM providers

Specra keeps Ollama as the local default and supports xAI's Grok API and OpenRouter through the shared structured-output client. Every response is validated against the same Pydantic schema used by the agents. Per-agent hosted model IDs can be configured without editing agent code.

See [docs/LLM_PROVIDERS.md](docs/LLM_PROVIDERS.md) for setup. Keep API keys in the backend's local `.env` or hosting secrets; never put them in frontend/Vite variables or commit them. Hosted API calls can incur costs. The repository CI uses mocked API responses and does not need provider credentials; run a small live smoke test only after configuring a key and verifying the selected model is available.

## Refinement branch: GenAI, testing, documents, and accounts

The public pull request linked below contains the current integrated feature set, built on the existing React/Vite and FastAPI project rather than rewriting it.

- **GenAI runtime:** Ollama remains the default, with configurable xAI Grok and OpenRouter adapters; see `docs/LLM_PROVIDERS.md`.
- **Orchestration:** the current four agents run through LangGraph with the existing stage callbacks and artifact names preserved.
- **Blueprint Quality Lab:** checks requirement traceability, missing coverage, invalid requirement references, open questions, and technical-review findings. It does not execute generated application code.
- **Project Copilot:** project-scoped answers grounded in saved artifacts and context, with proposed changes presented for approval.
- **Testing workspace:** creates requirement-linked proposed test cases and records execution outcomes separately. Proposed tests do not count as executed tests.
- **Engineering exports:** SRS, SDD, Test Report, and traceability matrix downloads.
- **Code Studio:** reviewable FastAPI + React/Vite source bundle generation and ZIP export; generated code is not run inside the Specra API process.
- **Accounts:** a one-time administrator bootstrap, login/logout, account management, and role-based project membership.
- **Public signup:** after the initial admin is initialized, the login screen offers `New to Specra? Create an account`. Self-registered accounts start as `viewer` and receive no project membership until assigned by an administrator/project owner. Set `ALLOW_PUBLIC_SIGNUP=false` to disable registration.

### Public deployment warning

These changes are on a review branch and are not live on the deployed website yet. Before merging/deploying the authenticated workspace, configure a server-only `AUTH_BOOTSTRAP_TOKEN`, set `AUTH_COOKIE_SECURE=true`, and use durable storage/managed database for existing project records. Render is configured for automatic deployment from `main`, so do not merge this feature set before backing up current project data and completing those settings.

Public registration is not email-verified in this iteration; newly created accounts have no access to private project records unless explicitly assigned to a project.
