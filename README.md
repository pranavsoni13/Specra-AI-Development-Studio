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
├── docs/
├── scripts/
├── tests/
└── README.md
```

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
