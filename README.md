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

## GenAI providers and model selection

Specra supports multiple backend LLM providers through a shared client. Ollama remains the local development default. Optional hosted provider modes are available for xAI Grok and OpenRouter, allowing the team to compare models against the same Specra prompts without changing each agent's implementation.

See [docs/LLM_PROVIDERS.md](docs/LLM_PROVIDERS.md) for environment variables and model ID formats. Put API keys only in the backend's local `.env` (ignored by Git) or backend hosting secrets. Never put provider keys in frontend/Vite environment variables or commit them.

Choose the deployed model after benchmarking representative projects for requirement coverage, Pydantic validation rate, latency, token usage, and API cost. A model available in the Grok consumer app does not automatically include API credits.

## Blueprint quality, test workspace, and downloadable documents

- **Blueprint Quality Lab** checks requirements-to-plan/architecture/API traceability, unknown requirement references, open clarifications, and reviewer findings. This is a blueprint consistency assessment; it does not execute generated application code.
- **Testing workspace** proposes requirement-linked test cases and tracks the result and execution notes entered by an authorized user. Proposed cases are not evidence of execution.
- **Downloadable engineering documents** include SRS, SDD, and a Test Report. Reports distinguish blueprint proposals from recorded test outcomes.
- **Code Studio / VS Code export** prepares a reviewable FastAPI + React/Vite starter bundle. Specra statically validates paths, secrets patterns, Python syntax, and JSON. It does not run model-generated code inside the API server; inspect the downloaded bundle before running it locally.

## Project access and roles

The authentication work adds sign-in and project membership roles for the people working on a project. The first administrator must be created through the configured bootstrap process, and protected API routes rely on project membership. Review [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md) and configure an appropriate bootstrap token and secure cookie settings before deploying the feature branch.
