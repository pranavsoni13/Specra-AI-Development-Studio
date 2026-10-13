# Specra

**From idea to engineered reality.**

Specra is an AI-assisted software engineering studio that coordinates specialized agents to turn a product brief into traceable engineering artifacts. It is built as a full-stack web application with a React frontend and a FastAPI backend.

> Project status: the local agent workflow and selected deterministic contract tests have passed. A production deployment still requires a publicly reachable inference endpoint and deployment-ready persistence/configuration.

## Live demo

- **Web app:** <https://specra-ai-development-studio.vercel.app>
- **Backend health:** <https://specra-api-pranavsoni13.onrender.com/health>
- **Interactive API docs:** <https://specra-api-pranavsoni13.onrender.com/docs>

The frontend and backend are deployed separately. The health endpoint confirms backend availability; successful AI generation additionally depends on the selected inference provider's credentials, model availability, and remaining provider quota.

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

## LLM provider configuration

Specra supports three provider modes through the shared structured-output client:

- `LLM_PROVIDER=ollama` (default): preserves local Ollama and Ollama Cloud behavior.
- `LLM_PROVIDER=xai`: uses the xAI chat-completions API through the OpenAI-compatible SDK.
- `LLM_PROVIDER=openrouter`: uses OpenRouter's OpenAI-compatible API to access a selected model.

Set provider credentials only in your local environment or deployment secret settings; never commit API keys.

| Setting | Purpose |
| --- | --- |
| `LLM_PROVIDER` | `ollama`, `xai`, or `openrouter`; defaults to `ollama`. |
| `XAI_API_KEY` | xAI API key when using `LLM_PROVIDER=xai`. |
| `OPENROUTER_API_KEY` | OpenRouter API key when using `LLM_PROVIDER=openrouter`. |
| `LLM_API_KEY` | Optional generic key fallback for either hosted provider. |
| `LLM_BASE_URL` | Optional override for an OpenAI-compatible provider base URL. |
| `XAI_REQUIREMENT_ANALYST_MODEL` | Optional model override for the Requirement Analyst with xAI. |
| `XAI_PROJECT_PLANNER_MODEL` | Optional model override for the Planner with xAI. |
| `XAI_SOFTWARE_ARCHITECT_MODEL` | Optional model override for the Architect with xAI. |
| `XAI_TECHNICAL_REVIEWER_MODEL` | Optional model override for the Reviewer with xAI. |
| `OPENROUTER_REQUIREMENT_ANALYST_MODEL` | Optional model ID override for the Requirement Analyst with OpenRouter. |
| `OPENROUTER_PROJECT_PLANNER_MODEL` | Optional model ID override for the Planner with OpenRouter. |
| `OPENROUTER_SOFTWARE_ARCHITECT_MODEL` | Optional model ID override for the Architect with OpenRouter. |
| `OPENROUTER_TECHNICAL_REVIEWER_MODEL` | Optional model ID override for the Reviewer with OpenRouter. |

Hosted defaults currently use `grok-4.7` for xAI and `x-ai/grok-4.7` for OpenRouter. Provider-scoped model settings take precedence. Existing role-specific model settings remain active for Ollama to preserve the current local setup. Model availability and pricing can change; verify current provider documentation before choosing production defaults.

Example for xAI (set these in your terminal/session or deployment environment, not in source code):

```text
LLM_PROVIDER=xai
XAI_API_KEY=<your-key>
```

Example for OpenRouter:

```text
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=<your-key>
OPENROUTER_TECHNICAL_REVIEWER_MODEL=<provider>/<model>
```

When switching the hosted deployment from Ollama Cloud to xAI/OpenRouter, update the provider and secret settings in the hosting dashboard first. Do not overwrite the working deployment's configuration as part of local development. Exercise the workflow against a fixed evaluation set before selecting a provider for all agents.

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
- A cloud-hosted backend cannot reach Ollama running only on a developer's computer. For Ollama Cloud, configure a reachable endpoint with `OLLAMA_HOST` and, when required, `OLLAMA_API_KEY`. For xAI or OpenRouter, use the `LLM_PROVIDER` and API-key settings described above.
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
