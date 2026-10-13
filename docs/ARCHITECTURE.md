# Specra architecture

Specra converts a software brief into versioned engineering artifacts using four agents.

## Request flow

1. React/Vite sends requests to `/api/v1`.
2. FastAPI stores a project and queues a workflow.
3. LangGraph invokes the Requirement Analyst node.
4. The Project Planner node creates milestones and tasks with canonical `FR-xxx` references.
5. The Software Architect node proposes components, API capabilities, data flow, assumptions, and decisions.
6. The Technical Reviewer node checks coverage, consistency, and unsupported additions.
7. Stage callbacks and artifact callbacks keep the existing live-progress UI and incremental artifact persistence working.
8. The backend stores artifacts, versions, and workflow events.

## Workflow design

The current graph is intentionally linear:

```text
START
  -> requirements
  -> project_plan
  -> architecture
  -> technical_review
  -> END
```

The four existing agent implementations, model selection, Pydantic artifact schemas, API response shapes, stage names, and frontend artifact names are preserved. Error handling emits the failed stage and re-raises the error; downstream nodes do not run after a failure. Conditional reviewer loops should be introduced only after retry limits and revised-artifact behavior are covered by deterministic tests.

RAG validation remains a separate service at this stage. Its integration should be the next workflow change, with a first-class report and explicit approval policy instead of silently folding validation findings into the technical review.

## State and project memory

- `ProjectStore` in `backend/app/core/storage/project_store.py` stores project state, artifacts, versions, and events.
- `ProjectContextStore` in `backend/app/core/context_store.py` stores user-provided context separately from generated artifacts.
- The next full workflow passes bounded saved context to Requirement Analyst. The current brief and explicit constraints override conflicting saved context.
- ChromaDB/sentence-transformers provide optional semantic context retrieval. This local embedding model is disabled by default on free hosting.

## Model providers

The shared LLM client defaults to Ollama and can also use xAI or OpenRouter through backend environment variables. See [LLM provider configuration](LLM_PROVIDERS.md). API keys must remain server-side. Provider/model choice should be validated on Specra's own regression prompts before being made the hosted default.

## Security and persistence risks

- The inspected project/context API routes do not currently apply a user identity or owner filter. Until authentication and project-level authorization are added, do not use the public hosted app for sensitive or private project data.
- The project store uses SQLite and optional vector data is stored on disk. Ephemeral cloud filesystems can lose these files after restarts or redeployments. Browser storage cannot recover server-side records that have been lost.
