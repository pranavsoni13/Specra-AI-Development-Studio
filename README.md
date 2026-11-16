# SPECRA — AI Development Studio

**From idea to engineered reality.**

SPECRA is an AI-assisted software engineering studio that converts a natural-language product brief into structured, traceable engineering artifacts. It coordinates specialized agents through a LangGraph workflow and provides a browser-based workspace for reviewing, refining, testing, documenting, and exporting project artifacts.

## Live application

- **Web application:** https://specra-ai-development-studio.vercel.app
- **Backend API:** https://specra-api-pranavsoni13.onrender.com
- **Health endpoint:** https://specra-api-pranavsoni13.onrender.com/health
- **Interactive API documentation:** https://specra-api-pranavsoni13.onrender.com/docs
- **Repository:** https://github.com/pranavsoni13/Specra-AI-Development-Studio

The frontend and backend are deployed separately. The frontend is hosted on Vercel and the FastAPI service is hosted on Render. Hosted application records use PostgreSQL through the configured `DATABASE_URL` (Neon in the production setup). The backend health endpoint confirms service health; it does not by itself prove that every model provider or individual workflow operation is functioning.

## Core engineering workflow

A project brief is processed through four specialized stages:

1. **Requirement Analyst** — extracts functional and non-functional requirements, assumptions, constraints, risks, and clarification questions. Functional requirements receive canonical references such as `FR-001`.
2. **Project Planner** — converts requirements into milestones, tasks, dependencies, and a development sequence while retaining requirement references.
3. **Software Architect** — proposes an architecture style, components, API capabilities, data flow, assumptions, and architecture decisions.
4. **Technical Reviewer** — checks requirement coverage, traceability, unsupported additions, and architectural consistency, and produces a structured review outcome.

The current LangGraph is a **linear four-node graph**:

```text
START
  -> requirements
  -> project_plan
  -> architecture
  -> technical_review
  -> END
```

Each stage emits progress and artifact callbacks. A stage failure is reported and propagated; downstream stages do not silently continue. Artifacts are stored with version history so users can review and refine generated work.

## Main features

- **Project workspace:** create and manage software projects and inspect workflow progress and generated artifacts.
- **Traceable requirements:** canonical functional requirement identifiers are carried into planning and architecture outputs.
- **Project Memory:** save project-specific notes, constraints, design decisions, references, and code excerpts. Saved context can be supplied as bounded secondary context to a later full workflow.
- **Project Copilot:** project-scoped conversational assistance grounded in saved project artifacts and context. Proposed refinements require user approval.
- **Blueprint Quality Lab:** deterministic checks over saved artifacts, including plan and architecture coverage, requirement-reference integrity, and open clarification findings. It evaluates the blueprint; it does not execute generated application code.
- **Testing Workspace:** generate requirement-linked test cases, save versioned test suites, and record execution outcomes separately from generated suggestions.
- **Engineering document exports:** produce Software Requirements Specification (SRS), Software Design Description (SDD), Test Report, and requirement traceability CSV exports.
- **Code Studio:** generate reviewable FastAPI and React/Vite starter bundles, preview files, run static validation, and export ZIP bundles. Generated code is not executed inside the SPECRA API process.
- **Artifact lifecycle:** review, refine, version, and restore supported project artifacts.
- **Team and permissions:** administrator-managed accounts, project membership, and project-scoped roles.

### Testing Workspace: an important distinction

Generating a test suite does **not** mean the tests have been executed. New suite versions start with cases marked `not_run`. Authorized users can record outcomes (`passed`, `failed`, or `blocked`) together with execution notes and environment details. Test reports must reflect recorded outcomes and must not describe suggested tests as passed without execution evidence.

## Authentication and access control

SPECRA uses server-side account and session records.

- The one-time `AUTH_BOOTSTRAP_TOKEN` is used only to initialize the first administrator in a fresh database. It is not required for ordinary login or public registration after initialization.
- Passwords are hashed with scrypt; raw session tokens are not stored in the database. The browser session cookie is HttpOnly and uses Secure in production.
- Public registration is enabled by default when the first administrator exists. Set `ALLOW_PUBLIC_SIGNUP=false` in the backend environment to disable it.
- Self-registered accounts receive the global `viewer` role by default. A viewer cannot access a private project until an administrator or project owner adds the account to that project.
- Global account roles and project membership roles are separate. Project membership determines access to a particular project and its permitted actions.
- Repeated failed sign-in attempts are throttled. Email verification, password-reset email, MFA, and SSO are not implemented in this iteration.

Never commit bootstrap tokens, passwords, API keys, database URLs, or other secrets. Do not place provider credentials in frontend variables.

## Technology stack

| Layer | Technologies |
|---|---|
| Frontend | React, JavaScript, Vite, CSS |
| Backend/API | Python, FastAPI, Uvicorn, Pydantic |
| Workflow orchestration | LangGraph |
| Model client | Ollama-compatible client and OpenAI-compatible hosted API adapters |
| Hosted LLM provider | OpenRouter in the current Render production configuration |
| Other supported providers | Ollama and xAI |
| Relational persistence | SQLite for local development; PostgreSQL for hosted deployment |
| Production database | Neon PostgreSQL via `DATABASE_URL` |
| Optional semantic retrieval | ChromaDB and sentence-transformers |
| Frontend hosting | Vercel |
| Backend hosting | Render |
| Tests/CI | pytest and GitHub Actions |

Package versions are not all pinned in `backend/requirements.txt`; the frontend package manifest declares React `^19.3.0` and Vite `^8.3.1`. The Render Blueprint specifies Python `3.11.11`.

## Model provider configuration

The backend selects its provider with `LLM_PROVIDER`. Ollama remains the default for local development. The current Render Blueprint selects `openrouter` and defines provider-scoped model overrides for the four workflow agents and Code Studio using `openai/gpt-4o`.

Required backend secret for the current hosted provider:

- `OPENROUTER_API_KEY`

Optional OpenRouter attribution settings:

- `OPENROUTER_SITE_URL`
- `OPENROUTER_APP_NAME`

The key must be configured only in the Render service's secret environment settings. Never add a real key to this repository or to the frontend. OpenRouter model access, account limits, and usage charges are controlled by the provider account.

For local or alternative-provider configuration, see [docs/LLM_PROVIDERS.md](docs/LLM_PROVIDERS.md).

## Repository layout

```text
Specra-AI-Development-Studio/
├── backend/
│   ├── app/
│   │   ├── agents/          # Requirement, planning, architecture, review,
│   │   │                    # testing, Copilot and code-generation agents
│   │   ├── api/routes/      # FastAPI route modules
│   │   ├── core/            # Database, security, stores, exports and providers
│   │   ├── rag/             # Optional project-context retrieval
│   │   └── workflows/       # LangGraph state and workflow
│   ├── requirements.txt
│   └── test_*.py
├── frontend/
│   ├── src/                 # React application and workspace panels
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

- Python 3.10 or newer (Python 3.11 is used by the hosted Render Blueprint)
- Node.js and npm
- Git
- Either local Ollama or credentials for a supported hosted model provider

### 1. Configure the model provider

For local Ollama, keep the default provider and pull the models used by the local role configuration:

```bash
ollama pull qwen3:1.7b
ollama pull qwen3:4b
```

For OpenRouter, set the following in an untracked backend `.env` file (never commit it):

```dotenv
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=replace-with-your-own-server-side-key
```

### 2. Start the backend

From the repository root:

```bash
cd backend
python -m venv .venv
```

Activate the environment, then install dependencies and start FastAPI:

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
- Interactive API documentation: `http://127.0.0.1:8000/docs`

### 3. Start the frontend

Open a second terminal at the repository root:

```bash
cd frontend
npm install
npm run dev
```

Vite serves the frontend at `http://localhost:5173` and proxies `/api` requests to the local backend at `http://127.0.0.1:8000` during development.

### 4. Initialize the first local administrator

For a fresh local database, configure a long random `AUTH_BOOTSTRAP_TOKEN` in the backend environment and use the application's first-admin initialization flow once. After the first administrator exists, ordinary sign-in and (when enabled) public registration do not require the bootstrap token. Keep the token private and do not reuse a production token in local development.

## Tests

The repository includes deterministic tests for provider configuration and response parsing, LangGraph orchestration, database adapter behavior, authentication and authorization, project storage, requirement traceability, refinement, Blueprint Quality Lab, testing workspace, and document exports.

Install the required test dependencies in the active backend virtual environment. From the repository root, run the focused deterministic suite:

```bash
# Windows Command Prompt
set PYTHONPATH=backend
python -m pytest -q backend/test_llm_providers.py backend/test_database_adapter.py backend/test_workflow_graph.py backend/test_semantic_integrity.py backend/test_refinement_flow.py backend/test_quality_lab.py backend/test_document_export_formats.py

# macOS/Linux
PYTHONPATH=backend python -m pytest -q backend/test_llm_providers.py backend/test_database_adapter.py backend/test_workflow_graph.py backend/test_semantic_integrity.py backend/test_refinement_flow.py backend/test_quality_lab.py backend/test_document_export_formats.py
```

The deterministic workflow tests mock agent/model calls. They validate orchestration and contracts; they do not prove live model quality, provider uptime, or production latency. Authentication tests use temporary test databases and must not be pointed at the production database.

GitHub Actions runs deterministic checks on pushes to `main` and selected feature branches and on pull requests to `main`. See [.github/workflows/deterministic-tests.yml](.github/workflows/deterministic-tests.yml).

## Production deployment

The current deployment is split across three services:

- **Vercel:** React/Vite frontend.
- **Render:** FastAPI/Uvicorn backend. The Render Blueprint uses the `backend` root directory, installs `requirements.txt`, starts Uvicorn on Render's assigned `PORT`, and checks `/health`.
- **Neon:** managed PostgreSQL used by the hosted application through the backend-only `DATABASE_URL`.

The hosted Render configuration requires durable PostgreSQL storage (`REQUIRE_PERSISTENT_DATABASE=true`). Authentication is unavailable when durable storage is required but not configured; this prevents silently relying on an ephemeral SQLite file on hosted infrastructure. Local development can continue to use SQLite.

Important backend environment variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection URI (secret) |
| `REQUIRE_PERSISTENT_DATABASE` | Require durable hosted storage |
| `AUTH_BOOTSTRAP_TOKEN` | One-time first-admin initialization secret |
| `AUTH_COOKIE_SECURE` | Secure session cookie setting |
| `ALLOW_PUBLIC_SIGNUP` | Enable/disable public registration |
| `LLM_PROVIDER` | Select `ollama`, `xai`, or `openrouter` |
| `OPENROUTER_API_KEY` | OpenRouter credential (secret) |

Do not include actual values of these variables in documentation, screenshots, GitHub issues, or source control. ChromaDB retrieval data is separate from relational application records; optional project-context vector indexing is controlled by `ENABLE_PROJECT_CONTEXT_RAG` and may be disabled on memory-constrained hosting.

For the hosted database and deployment procedure, see [docs/PERSISTENT_DATABASE.md](docs/PERSISTENT_DATABASE.md) and [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Project memory and workspace restoration

- Project Memory is stored server-side and scoped to a project.
- A subsequent full workflow can use a bounded set of saved sources as secondary context. The current brief and explicit constraints take precedence over conflicting saved context.
- Browser storage may remember the last selected project, artifact, or scroll position; it is not a replacement for server-side persistence.
- Project artifacts are stored with version history and workflow events.
- Optional vector retrieval is separate from relational project persistence and can be rebuilt from source context where configured.

## Known limitations

- Model outputs depend on provider availability, model access, prompts, and structured-output compliance. Pydantic validation checks response structure but does not guarantee factual correctness.
- The core four-stage workflow is linear; it does not currently implement an automatic reviewer retry loop.
- Generated test cases are not executed automatically. Execution status is recorded separately by authorized users.
- Code Studio performs static checks and produces reviewable bundles; it does not run generated code inside the API process.
- Public self-registration is not email-verified in this iteration. Password reset by email, MFA, SSO, and distributed rate limiting are not implemented.
- Optional semantic retrieval can be disabled on low-memory hosting.
- A healthy backend health endpoint does not establish that every model, export, or user workflow is error-free; validate those features with representative smoke tests.

## License

This project is distributed under the MIT License. See [LICENSE](LICENSE).
