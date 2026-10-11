# Specra deployment notes

## Services
- Frontend: Vercel static Vite deployment.
- Backend: Render running FastAPI/Uvicorn.
- Inference: Ollama Cloud through `OLLAMA_HOST` and `OLLAMA_API_KEY`.

Set `OLLAMA_API_KEY` in the Render environment panel, never in source control. Keep these model variables aligned with models available to your Ollama account:

- `OLLAMA_HOST=https://ollama.com`
- `REQUIREMENT_ANALYST_MODEL`
- `PROJECT_PLANNER_MODEL`
- `SOFTWARE_ARCHITECT_MODEL`
- `TECHNICAL_REVIEWER_MODEL`

## Persistence warning
The app uses SQLite for projects and saved project context. Render Free filesystems are ephemeral; restarts or redeploys can lose local SQLite contents. Use durable storage or an external database before relying on hosted projects long-term.

Semantic project-context indexing is disabled unless `ENABLE_PROJECT_CONTEXT_RAG=true`; enabling it loads a local sentence-transformer and ChromaDB and may exceed low-memory hosting limits.

## Quick checks
- `GET /health`
- `GET /docs`
- `GET /api/v1/projects`
- Create a project, add Project Memory, then use **Run All Again**.
