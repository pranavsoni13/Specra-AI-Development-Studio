# Specra Testing Workspace and Engineering Documents

This document describes the first testing/document milestone on `feature/testing-docs-copilot-2026-10`. It uses the existing requirements, plan, architecture, project-membership, and structured-LLM infrastructure.

## Workflow

1. Run the existing Specra requirements/planning/architecture workflow.
2. Open a project and choose **Testing & Docs**.
3. Generate a new test suite. The Testing Agent maps cases to canonical `FR-001` IDs using the saved requirements artifact.
4. Review each test's type, priority, setup, steps, expected result, and source.
5. The generated suite is saved as a version. Each new suite version starts with all tests marked `not_run`.
6. An authorized Tester, Developer, project owner, or admin may manually record a result, execution environment, and evidence notes.
7. Download the SRS, SDD, Test Report, and Traceability Matrix (CSV). These exports use the latest saved artifacts and test suite.

## Generated tests are not automatically executed

The current milestone creates test designs. It does not execute generated application code, run tests against a project-specific IDE, or claim successful test execution from a language-model response.

A test result marked `passed`, `failed`, or `blocked` is a human-recorded outcome from the authorized Testing workspace. The report includes environment/evidence fields and should be completed honestly. Automated runner integration is a later milestone and must run in an isolated sandbox.

## API endpoints

All endpoints require a signed-in session and access to the named project.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/v1/projects/{project_id}/tests` | Return latest suite, version history, and caller's project role |
| POST | `/api/v1/projects/{project_id}/tests/generate` | Generate and persist a new suite version |
| PATCH | `/api/v1/projects/{project_id}/tests/cases/{test_id}/result` | Record status, environment, and notes for a test case |
| GET | `/api/v1/projects/{project_id}/tests/history` | List version metadata |
| GET | `/api/v1/projects/{project_id}/documents/srs` | Download Software Requirements Specification (Markdown) |
| GET | `/api/v1/projects/{project_id}/documents/sdd` | Download Software Design Description (Markdown) |
| GET | `/api/v1/projects/{project_id}/documents/test-report` | Download test outcomes and evidence (Markdown) |
| GET | `/api/v1/projects/{project_id}/documents/traceability` | Download requirements traceability (CSV) |

The current role rules permit project owners/admins to manage project testing, and allow the assigned `tester` or `developer` role to record outcomes. An analyst can generate cases. Readers may download reports for projects they are allowed to access.

## Design notes

- Test-suite versions are stored separately from the core project artifacts so the original SRS/SDD artifact schemas and current dashboard do not have to change.
- The test generator uses the existing shared LLM client and Pydantic validation. Provider selection can be configured by the separate provider-refinement milestone.
- Unknown requirement references from the model are discarded with a coverage warning.
- Requirements that do not receive a usable generated case get an explicitly labelled deterministic fallback case so the coverage gap remains visible.
- Document exports use the saved artifact versions; they do not silently regenerate content.
- Traceability currently reports requirement presence across plan tasks/milestones, architecture components/API/decisions, technical-review coverage, and test cases. It is a practical matrix, not formal certification.

## Tests

From `backend/`:

```bash
python test_testing_workspace.py
python test_testing_routes.py
python test_auth_security.py
python test_auth_routes.py
```

The CI workflow also compiles the application, imports the FastAPI app, and builds the Vite frontend. It uses mocked model responses and temporary SQLite files; no external API call is required for the deterministic tests.

## Next milestone: IDE integration and code generation

The next milestone should first export a reproducible starter-project bundle for a selected stack (for example React + FastAPI), with a file manifest and a diff preview. Automated validation should then run in a restricted container with time, memory, network, and filesystem boundaries. Arbitrary generated code must never execute inside Specra's main API process or inherit provider/production credentials. Only after that loop is dependable should direct IDE and CI/CD integration be added.
