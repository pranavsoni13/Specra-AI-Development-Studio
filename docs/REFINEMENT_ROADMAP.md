# Specra Refinement Roadmap

This roadmap refines the existing repository in small, reviewable increments. It is not a rewrite plan. Keep the current React/Vite dashboard, FastAPI API, agent classes, schemas, refinement service, artifact versioning, and project-memory functionality unless a concrete regression or requirement justifies a change.

## Product objective

Evolve Specra from a project-brief-to-engineering-blueprint generator into a trustworthy AI software-development workspace that can plan, design, explain, generate, test, and document software.

## Workstreams and acceptance criteria

### 0. Safe baseline and regression coverage
- Work on a feature branch and keep `main`/production untouched until changes are reviewed.
- Run deterministic contract tests and frontend production build; label any tests that need a running model separately.
- Record current API response shapes, stage names, artifact schemas, and version-history behavior.
- Confirm that tests do not modify or delete production/user project data.

**Done when:** a repeatable baseline is documented and regressions can be detected before merge.

### 1. Provider-flexible GenAI runtime
- Keep Ollama local and Ollama Cloud as supported modes.
- Add xAI and OpenRouter through an OpenAI-compatible client behind the existing shared structured-output interface.
- Keep API keys in environment/deployment secrets only; provide provider-scoped model overrides.
- Validate every provider response through the existing Pydantic schemas and quality controllers.
- Track provider/model and token usage where returned, and provide a cost-control policy before wider use.
- Do not declare one provider categorically better without evaluating it on the same fixed project prompts and scoring rubric.

**Done when:** each provider can complete a small structured-output smoke test, invalid JSON is rejected, auth/rate-limit errors stay visible, and the chosen provider can be changed without editing agent business logic.

### 2. Workflow orchestration and grounded validation
- Route the current Requirement Analyst, Planner, Architect, and Technical Reviewer through LangGraph while preserving stage callback events and artifact publishing.
- Integrate the separately implemented RAG validator after architecture generation.
- Save a RAG-validation artifact/findings and make the final review consider grounded evidence without treating missing corpus evidence as absolute proof that a design is wrong.
- Use deterministic gates for required fields, requirement coverage, and unsafe/unsupported scope changes; use LLMs as assistance, not as the sole authority.
- Add failure-state and retry-path tests.

**Done when:** stage order and emitted artifacts are stable; RAG findings are persisted; validation failures are visible; existing refinement and version histories continue to work.

### 3. Detailed testing workspace
- Add a dedicated testing area that maps functional requirements to test cases.
- Generate unit, API/integration, and acceptance-test suggestions from approved requirements and architecture.
- Show test ID, linked requirement IDs (for example, `FR-001`), setup, steps, expected result, priority, and execution status.
- Start with human-reviewable test cases and downloadable reports; only mark tests as executed when an actual runner ran them.
- Later execute generated tests in a sandbox/container with no production credentials, bounded CPU/memory/time, restricted network access, and captured logs.

**Done when:** users can inspect requirement coverage, distinguish generated versus executed tests, and export a dated test report containing the actual results and known limitations.

### 4. Distinctive Specra AI Copilot
- Add a chat surface in the existing dashboard, scoped to the currently selected project.
- Ground answers in that project's brief, requirements, plan, architecture, review, RAG findings, and explicitly selected memory sources.
- Cite the artifact/requirement used for project-specific claims and say when the project has no supporting evidence.
- Offer suggested changes as previews; require user approval before mutating saved artifacts.
- Reuse the provider runtime and project-context retrieval rather than creating a disconnected second LLM implementation.

**Done when:** the Copilot can explain the current project accurately, identify relevant artifacts, propose refinements, and never silently overwrites project records.

### 5. Downloadable engineering documents
- Render the current structured artifacts into consistent, titled documents:
  - Software Requirements Specification (SRS)
  - Software Design Description (SDD)
  - Test Plan / Test Report
  - Project Plan and Architecture Summary
- Support downloadable Markdown and JSON first; add PDF/DOCX formats with consistent metadata, dates, project/version identifiers, and a clear distinction between draft, approved, and executed results.
- Ensure exports use the exact saved artifact versions. Never invent test pass counts or approval status.
- Test document generation with empty, partial, long, and Unicode-containing artifacts.

**Done when:** each report is downloadable, readable, version-traceable, and covered by deterministic tests.

### 6. Authentication and role-based access
- Establish identity/session handling before exposing real user projects to multiple users.
- Define least-privilege roles as a starting point: Project Owner, Developer, Reviewer, and Read-only Viewer.
- Enforce authorization in backend routes and ownership checks in data access; hiding buttons in the frontend is not access control.
- Scope project listings, project context, artifacts, versions, exports, and Copilot conversations to the authorized user/team.
- Add tests for unauthenticated requests, cross-user project IDs, role-permission boundaries, and secret redaction.
- Keep a local single-user development path if possible, but do not leave public write/read endpoints open for shared production use.

**Done when:** API authorization—not just UI visibility—prevents unauthorized project and artifact access, and tests demonstrate this.

### 7. Project data durability and operations
- Decide on durable storage for projects, artifact versions, events, context documents, and vector indexes before relying on hosted persistence.
- Add migration/backup/restore procedures, provider timeout/rate-limit handling, bounded concurrency, and operational logs that exclude secrets and unnecessary prompt data.
- Add health/readiness diagnostics that distinguish API health from LLM provider availability and RAG readiness.
- Add per-user/team quotas and model-spend limits before public availability.

**Done when:** a controlled restart/redeploy test preserves the records that the product claims to preserve, and failures are visible without exposing secrets.

### 8. Blueprint-to-code generation and testing
- Generate a file manifest and source files only from an approved blueprint.
- Show generated files as a reviewable diff before export.
- Run static checks and generated tests in an isolated execution environment; feed failures back as suggestions, with bounded repair attempts.
- Never execute arbitrary generated code inside the main API process or grant it production credentials.
- Export a code bundle first; add Git, IDE, and CI/CD integration only after the local generation/test lifecycle is reliable.

**Done when:** a user can inspect and download a generated starter project, see which checks actually ran, and review changes before accepting them.

### 9. Multi-user collaboration and longer-term scope
- After authentication, authorization, storage, and audit trails are stable, support shared workspaces, reviewer comments, and explicit version approvals.
- Evaluate multi-language/framework templates and self-improvement from curated, consented project outcomes; do not train on private project content by default.

## Fixed evaluation set for provider comparison

Create a versioned, privacy-safe suite of representative briefs:
1. Small CRUD application with explicit scope boundaries.
2. Application requiring authentication and role permissions.
3. Application with conflicting requirements or missing decisions.
4. Application with non-functional constraints (cost, performance, accessibility).
5. Architecture requiring evidence-backed trade-offs.

Score each provider on:
- Schema validity and quality-controller pass rate.
- Requirement coverage and traceability integrity.
- Unrequested feature/scope additions.
- Architecture consistency and factual grounding.
- Latency and failure rate.
- Input/output token usage and estimated cost.
- Repeatability across multiple runs.

Use the same prompt, schemas, settings, and evaluation cases for each model. Treat the results as measurements, not marketing claims.

## Delivery discipline

- Land each workstream in a small pull request with deterministic tests.
- Do not merge/deploy merely because a commit was pushed.
- Do not run destructive migrations or modify live user data during development.
- Never commit API keys, local databases, raw project memory, model weights, or generated vector-store runtime data.
- Update this roadmap when acceptance criteria change, not instead of implementing them.
