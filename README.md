# Specra

**From idea to engineered reality.**

Specra is an AI-assisted software engineering studio that coordinates specialized agents to turn a product brief into traceable engineering artifacts. It is built as a full-stack web application with a React frontend and a FastAPI backend.

> Project status: the local agent workflow and selected deterministic contract tests have passed. A production deployment still requires a publicly reachable inference endpoint and deployment-ready persistence/configuration.

## Live demo

- **Web app:** <https://specra-ai-development-studio.vercel.app>
- **Backend health:** <https://specra-api-pranavsoni13.onrender.com/health>
- **Interactive API docs:** <https://specra-api-pranavsoni13.onrender.com/docs>

The frontend and backend are deployed separately. The health endpoint confirms backend availability; successful AI generation additionally depends on the configured inference endpoint, valid provider credentials, available model access, and remaining provider usage.

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
- **Agent/model runtime:** Ollama by default; optional xAI and OpenRouter adapters
- **Workflow and retrieval:** LangGraph, ChromaDB, sentence-transformers
- **Local persistence:** SQLite

## LLM provider configuration

Ollama remains the default and preserves the local development workflow. The shared model client also supports xAI and OpenRouter through backend environment variables. See [docs/LLM_PROVIDERS.md](docs/LLM_PROVIDERS.md) for the exact variables, model ID formats, and security notes. API keys must remain server-side and must never be committed.

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
├── docs/
├── knowledge/documents/
├── scripts/
├── render.yaml
└── README.md
```

## Run locally

### Prerequisites

- Python 3.10 or newer
- Node.js and npm
- Ollama for the default local setup, or credentials for a supported hosted provider
- Enough memory to run the selected local models when using Ollama

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
.venv\\Scripts\\activate

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

Install test tooling in your active backend virtual environment:

```bash
pip install pytest
```

Run the deterministic regression suite from the repository root:

```bash
# Windows Command Prompt
set PYTHONPATH=backend
python -m pytest -q backend/test_llm_providers.py backend/test_workflow_graph.py backend/test_semantic_integrity.py backend/test_refinement_flow.py

# macOS/Linux
PYTHONPATH=backend python -m pytest -q backend/test_llm_providers.py backend/test_workflow_graph.py backend/test_semantic_integrity.py backend/test_refinement_flow.py
```

These tests mock model calls; they do not require a working Ollama server or a paid API key. The provider adapter has not yet been live-tested against xAI or OpenRouter credentials, so run one small smoke test after configuring your chosen provider.

Run the full multi-agent workflow with:

```bash
python test_project_workflow.py
```

The full workflow invokes language models and may take a long time on CPU-only hardware. It is not necessary to rerun it for routine documentation or frontend changes.

## Deployment notes

The frontend and backend are separate deployment concerns.

- The Vite proxy in `frontend/vite.config.js` applies to local development, not to a production deployment.
- The backend needs an inference endpoint reachable from the deployed service. Provider-specific variables belong in the backend environment, not in frontend source code.
- The project currently uses SQLite for project/context storage and ChromaDB for optional retrieval. Ephemeral cloud filesystems can lose SQLite and generated vector-store files after restarts or redeployments. Use durable storage before relying on long-term hosted project data.
- Do not commit `.env` files, API keys, local databases, model weights, vector database runtime files, virtual environments, or build output.

## License

This project is distributed under the MIT License. See [LICENSE](LICENSE).

## Project memory and workspace restoration

- **Project Memory** stores project-scoped notes, constraints, design decisions, references, and code excerpts using the project-context API.
- The next **Run All Again** supplies up to eight saved sources (bounded to 12,000 characters) as secondary context to requirement analysis. The current brief and explicit constraints take precedence over conflicting saved context.
- The browser remembers the last project, selected artifact, and scroll position. Browser storage cannot recover server-side records that have been lost.
- Hosted SQLite and vector files need durable database/storage before relying on projects surviving backend restarts and redeploys.
- Project-context vector indexing is opt-in with `ENABLE_PROJECT_CONTEXT_RAG=true`. It is disabled by default on low-memory hosting; saved text still works as context for the full workflow without a vector index.
