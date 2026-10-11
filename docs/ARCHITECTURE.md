# Specra architecture

Specra converts a software brief into versioned engineering artifacts using four agents.

## Request flow
1. React/Vite sends requests to `/api/v1`.
2. FastAPI stores a project and queues a workflow.
3. Requirement Analyst creates the primary requirements artifact.
4. Project Planner creates milestones and tasks with canonical `FR-xxx` references.
5. Software Architect proposes components, API capabilities, data flow, assumptions, and decisions.
6. Technical Reviewer checks coverage, consistency, and unsupported additions.
7. The backend stores artifacts, versions, and workflow events.

## State and project memory
- `ProjectStore` in `backend/app/core/storage/project_store.py` stores project state, artifacts, versions, and events.
- `ProjectContextStore` in `backend/app/core/context_store.py` stores user-provided context separately from generated artifacts.
- The next full workflow passes bounded saved context to Requirement Analyst. The current brief and explicit constraints override conflicting saved context.
- ChromaDB/sentence-transformers provide optional semantic context retrieval. This local embedding model is disabled by default on free hosting.

## Persistence limitation
The frontend restores the last project, artifact selection, and scroll position. The backend still needs durable storage; browser state cannot recover data lost from an ephemeral server filesystem.
