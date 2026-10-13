from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from typing import Literal

from app.agents.project_planner.schemas import ProjectPlan
from app.agents.requirement_analyst.schemas import RequirementAnalysis
from app.agents.software_architect.schemas import SystemArchitecture
from app.agents.technical_reviewer.schemas import ReviewReport

from app.core.context_store import project_context_store
from app.core.errors.exceptions import AgentExecutionError
from app.core.refinement.service import ArtifactRefinementService
from app.core.security import (
    auth_store,
    get_current_user,
    require_project_roles,
    require_roles,
    require_stage_role,
)
from app.core.storage.project_store import (
    STAGES,
    project_store,
)
from app.workflows.project_workflow import ProjectWorkflow


router = APIRouter(
    prefix="/api/v1/projects",
    tags=["Projects"],
    dependencies=[Depends(get_current_user)],
)


_WORKFLOW_EXECUTOR = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="ai-project-workflow",
)


# =========================================================
# Schemas
# =========================================================


class ProjectCreateRequest(BaseModel):
    idea: str = Field(
        min_length=1,
        description="The user's software idea or problem statement.",
    )


class ProjectAnalysisRequest(BaseModel):
    idea: str = Field(
        min_length=1,
        description="The user's software idea or problem statement.",
    )


class RefinementRequest(BaseModel):
    instruction: str = Field(
        min_length=1,
        description="Natural-language refinement instruction.",
    )


class ProjectMemberRequest(BaseModel):
    email: EmailStr
    role: Literal[
        "analyst", "planner", "architect", "tester",
        "reviewer", "developer", "viewer",
    ] = "viewer"


class ProjectSummary(BaseModel):
    project_id: str
    idea: str
    project_name: str | None = None
    status: str
    current_stage: str
    stage_status: str
    stages: dict[str, str]
    approved: bool | None = None
    error: str | None = None
    artifact_versions: dict[str, int]
    created_at: datetime
    updated_at: datetime


class ProjectArtifactResponse(BaseModel):
    project_id: str
    project_name: str | None = None
    status: str
    current_stage: str
    stage_status: str
    stages: dict[str, str]
    approved: bool | None = None
    requirements: dict | None = None
    project_plan: dict | None = None
    architecture: dict | None = None
    review: dict | None = None
    artifact_versions: dict[str, int]
    created_at: datetime
    updated_at: datetime


class ProjectRunResponse(BaseModel):
    project_id: str
    project_name: str | None = None
    status: str
    current_stage: str
    stage_status: str
    stages: dict[str, str]
    approved: bool | None = None
    requirements: dict | None = None
    project_plan: dict | None = None
    architecture: dict | None = None
    review: dict | None = None
    error: str | None = None
    artifact_versions: dict[str, int]
    created_at: datetime
    updated_at: datetime


class ProjectVersionResponse(BaseModel):
    artifact_version_id: int
    project_id: str
    stage: str
    version_number: int
    content: dict
    instruction: str | None = None
    source: str
    created_at: datetime


class ProjectEventResponse(BaseModel):
    event_id: int
    project_id: str
    event_type: str
    stage: str | None = None
    message: str | None = None
    data: dict | None = None
    created_at: datetime


class ProjectAnalysisResponse(BaseModel):
    project_id: str
    project_name: str
    status: str
    approved: bool
    requirements: dict
    project_plan: dict
    architecture: dict
    review: dict


# =========================================================
# Helpers
# =========================================================


def _get_project(
    project_id: str,
) -> dict:

    project = project_store.get_project(
        project_id
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Project '{project_id}' not found."
            ),
        )

    return project


def _to_datetime(
    value: str,
) -> datetime:
    return datetime.fromisoformat(
        value
    )


def _build_summary(
    project: dict,
) -> ProjectSummary:

    return ProjectSummary(
        project_id=project["project_id"],
        idea=project["idea"],
        project_name=project["project_name"],
        status=project["status"],
        current_stage=project["current_stage"],
        stage_status=project["stage_status"],
        stages=project["stages"],
        approved=project["approved"],
        error=project["error"],
        artifact_versions=(
            project["artifact_versions"]
        ),
        created_at=_to_datetime(
            project["created_at"]
        ),
        updated_at=_to_datetime(
            project["updated_at"]
        ),
    )


def _build_artifacts(
    project: dict,
) -> ProjectArtifactResponse:

    artifacts = (
        project_store.get_artifacts(
            project["project_id"]
        )
    )

    versions = (
        project_store.get_latest_version_numbers(
            project["project_id"]
        )
    )

    return ProjectArtifactResponse(
        project_id=project["project_id"],
        project_name=project["project_name"],
        status=project["status"],
        current_stage=project["current_stage"],
        stage_status=project["stage_status"],
        stages=project["stages"],
        approved=project["approved"],
        requirements=artifacts["requirements"],
        project_plan=artifacts["project_plan"],
        architecture=artifacts["architecture"],
        review=artifacts["technical_review"],
        artifact_versions=versions,
        created_at=_to_datetime(
            project["created_at"]
        ),
        updated_at=_to_datetime(
            project["updated_at"]
        ),
    )


def _build_run_response(
    project: dict,
) -> ProjectRunResponse:

    artifacts = (
        project_store.get_artifacts(
            project["project_id"]
        )
    )

    versions = (
        project_store.get_latest_version_numbers(
            project["project_id"]
        )
    )

    return ProjectRunResponse(
        project_id=project["project_id"],
        project_name=project["project_name"],
        status=project["status"],
        current_stage=project["current_stage"],
        stage_status=project["stage_status"],
        stages=project["stages"],
        approved=project["approved"],
        requirements=artifacts["requirements"],
        project_plan=artifacts["project_plan"],
        architecture=artifacts["architecture"],
        review=artifacts["technical_review"],
        error=project["error"],
        artifact_versions=versions,
        created_at=_to_datetime(
            project["created_at"]
        ),
        updated_at=_to_datetime(
            project["updated_at"]
        ),
    )


def _artifact_to_model(
    stage: str,
    content: dict,
):
    if stage == "requirements":
        return RequirementAnalysis.model_validate(
            content
        )

    if stage == "project_plan":
        return ProjectPlan.model_validate(
            content
        )

    if stage == "architecture":
        return SystemArchitecture.model_validate(
            content
        )

    if stage == "technical_review":
        return ReviewReport.model_validate(
            content
        )

    raise ValueError(
        f"Unknown artifact stage: {stage}"
    )


_STAGE_LABELS = {
    "requirements": "Requirements",
    "project_plan": "Project Plan",
    "architecture": "Architecture",
    "technical_review": "Technical Review",
}


_STAGE_PREREQUISITES = {
    "requirements": (),
    "project_plan": ("requirements",),
    "architecture": (
        "requirements",
        "project_plan",
    ),
    "technical_review": (
        "requirements",
        "project_plan",
        "architecture",
    ),
}


def _check_stage_dependencies(
    project_id: str,
    stage: str,
) -> None:
    """
    Prevent an artifact from being regenerated while an upstream
    dependency is missing or not completed.

    This is deliberately deterministic. It avoids spending several
    minutes on a local LLM call when the requested stage cannot yet
    produce a valid result.
    """

    project = project_store.get_project(
        project_id
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Project '{project_id}' not found."
            ),
        )

    missing: list[str] = []

    for prerequisite in _STAGE_PREREQUISITES[stage]:
        stage_status = project["stages"].get(
            prerequisite
        )

        artifact = project_store.get_latest_artifact(
            project_id,
            prerequisite,
        )

        if (
            stage_status != "completed"
            or artifact is None
        ):
            missing.append(
                _STAGE_LABELS[prerequisite]
            )

    if missing:
        current_label = _STAGE_LABELS[stage]
        missing_text = ", ".join(missing)

        raise HTTPException(
            status_code=409,
            detail=(
                f"{current_label} is blocked because the required "
                f"upstream stage(s) are not completed: {missing_text}. "
                "Rebuild the affected upstream stage first."
            ),
        )


def _load_artifact_models(
    project_id: str,
):
    artifacts = project_store.get_artifacts(
        project_id
    )

    missing = [
        stage
        for stage in STAGES
        if artifacts.get(stage) is None
    ]

    if missing:
        raise ValueError(
            "Project does not contain a complete artifact set. "
            f"Missing: {missing}"
        )

    requirements = (
        RequirementAnalysis.model_validate(
            artifacts["requirements"]
        )
    )

    project_plan = (
        ProjectPlan.model_validate(
            artifacts["project_plan"]
        )
    )

    architecture = (
        SystemArchitecture.model_validate(
            artifacts["architecture"]
        )
    )

    review = (
        ReviewReport.model_validate(
            artifacts["technical_review"]
        )
    )

    return (
        requirements,
        project_plan,
        architecture,
        review,
    )


# =========================================================
# Workflow callbacks
# =========================================================


def _update_stage(
    project_id: str,
    stage: str,
    stage_status: str,
) -> None:

    project_store.set_stage_status(
        project_id,
        stage,
        stage_status,
        current_stage=stage,
        project_status="running",
    )


def _update_artifact(
    project_id: str,
    stage: str,
    artifact,
    *,
    instruction: str | None = None,
    source: str = "workflow",
) -> None:

    content = artifact.model_dump()

    project_store.save_artifact(
        project_id,
        stage,
        content,
        instruction=instruction,
        source=source,
    )

    if stage == "requirements":
        project_store.update_project(
            project_id,
            project_name=artifact.project_name,
        )

    if stage == "technical_review":
        project_store.update_project(
            project_id,
            approved=(
                artifact.overall_status
                == "PASS"
            ),
        )


# =========================================================
# Full workflow worker
# =========================================================


MAX_PROJECT_CONTEXT_CHARS = 12000
MAX_PROJECT_CONTEXT_SOURCES = 8


def _format_project_context(project_id: str) -> str | None:
    """Build a bounded, source-labelled memory block for the next full run."""
    records = project_context_store.list_context(project_id)[:MAX_PROJECT_CONTEXT_SOURCES]
    blocks: list[str] = []
    remaining = MAX_PROJECT_CONTEXT_CHARS

    for record in records:
        name = str(record.get("name") or "Untitled source")
        kind = str(record.get("kind") or "note")
        content = str(record.get("content") or "").strip()
        header = f"[Source: {name} | Type: {kind}]\n"
        if not content or remaining <= len(header):
            continue

        body = content[: max(0, remaining - len(header))]
        if len(body) < len(content):
            body += "\n[Source clipped to fit the project-context limit.]"

        block = header + body
        blocks.append(block)
        remaining -= len(block) + 2
        if remaining <= 0:
            break

    return "\n\n".join(blocks) if blocks else None


def _run_project_job(
    project_id: str,
) -> None:

    project = (
        project_store.get_project(
            project_id
        )
    )

    if project is None:
        return

    try:
        workflow = ProjectWorkflow()
        project_context = _format_project_context(project_id)

        result = workflow.run(
            project["idea"],
            project_context=project_context,
            on_stage=lambda stage, stage_status: (
                _update_stage(
                    project_id,
                    stage,
                    stage_status,
                )
            ),
            on_artifact=lambda stage, artifact: (
                _update_artifact(
                    project_id,
                    stage,
                    artifact,
                    source="workflow",
                )
            ),
        )

        for stage, artifact in [
            (
                "requirements",
                result.requirements,
            ),
            (
                "project_plan",
                result.project_plan,
            ),
            (
                "architecture",
                result.architecture,
            ),
            (
                "technical_review",
                result.review,
            ),
        ]:
            existing = (
                project_store.get_latest_artifact(
                    project_id,
                    stage,
                )
            )

            latest_content = (
                artifact.model_dump()
            )

            if (
                existing is None
                or existing["content"]
                != latest_content
            ):
                _update_artifact(
                    project_id,
                    stage,
                    artifact,
                    source="workflow",
                )

        project_store.update_project(
            project_id,
            project_name=(
                result.requirements.project_name
            ),
            status="completed",
            current_stage="completed",
            stage_status="completed",
            approved=result.approved,
            error=None,
        )

        project_store.add_event(
            project_id,
            "workflow_completed",
            message="Full project workflow completed.",
        )

    except ValueError as exc:

        project_store.update_project(
            project_id,
            status="failed",
            stage_status="failed",
            error=str(exc),
        )

        project_store.add_event(
            project_id,
            "workflow_failed",
            message=str(exc),
        )

    except AgentExecutionError as exc:

        project_store.update_project(
            project_id,
            status="failed",
            stage_status="failed",
            error=str(exc),
        )

        project_store.add_event(
            project_id,
            "workflow_failed",
            message=str(exc),
        )

    except Exception as exc:

        project_store.update_project(
            project_id,
            status="failed",
            stage_status="failed",
            error=str(exc),
        )

        project_store.add_event(
            project_id,
            "workflow_failed",
            message=str(exc),
        )


# =========================================================
# Refinement worker
# =========================================================


def _run_refinement_job(
    project_id: str,
    mode: str,
    instruction: str,
) -> None:

    try:
        service = ArtifactRefinementService()

        (
            requirements,
            project_plan,
            architecture,
            review,
        ) = _load_artifact_models(
            project_id
        )

        # -------------------------------------------------
        # Requirements
        # -------------------------------------------------

        if mode in {
            "requirements",
            "global",
        }:

            _update_stage(
                project_id,
                "requirements",
                "running",
            )

            requirements = (
                service.refine_requirements(
                    idea=(
                        project_store.get_project(
                            project_id
                        )["idea"]
                    ),
                    current_requirements=(
                        requirements
                    ),
                    instruction=instruction,
                )
            )

            _update_artifact(
                project_id,
                "requirements",
                requirements,
                instruction=instruction,
                source="refinement",
            )

            _update_stage(
                project_id,
                "requirements",
                "completed",
            )

            project_store.update_project(
                project_id,
                project_name=(
                    requirements.project_name
                ),
            )

        # -------------------------------------------------
        # Planner
        # -------------------------------------------------

        if mode in {
            "requirements",
            "project_plan",
            "global",
        }:

            _update_stage(
                project_id,
                "project_plan",
                "running",
            )

            if mode == "project_plan":
                planner_instruction = (
                    instruction
                )
            else:
                planner_instruction = (
                    "Synchronize the existing project plan "
                    "with the updated authoritative requirements. "
                    "Preserve unaffected planning decisions and "
                    "ensure every functional requirement is covered."
                )

            project_plan = (
                service.refine_project_plan(
                    requirements=requirements,
                    current_plan=project_plan,
                    instruction=planner_instruction,
                )
            )

            _update_artifact(
                project_id,
                "project_plan",
                project_plan,
                instruction=planner_instruction,
                source="refinement",
            )

            _update_stage(
                project_id,
                "project_plan",
                "completed",
            )

        # -------------------------------------------------
        # Architecture
        # -------------------------------------------------

        if mode in {
            "requirements",
            "project_plan",
            "architecture",
            "global",
        }:

            _update_stage(
                project_id,
                "architecture",
                "running",
            )

            if mode in {
                "architecture",
                "global",
            }:
                architecture_instruction = (
                    instruction
                )
            else:
                architecture_instruction = (
                    "Synchronize the architecture with the "
                    "updated requirements and project plan. "
                    "Preserve unaffected architectural decisions."
                )

            architecture = (
                service.refine_architecture(
                    requirements=requirements,
                    project_plan=project_plan,
                    current_architecture=architecture,
                    instruction=architecture_instruction,
                )
            )

            _update_artifact(
                project_id,
                "architecture",
                architecture,
                instruction=architecture_instruction,
                source="refinement",
            )

            _update_stage(
                project_id,
                "architecture",
                "completed",
            )

        # -------------------------------------------------
        # Technical Review
        # -------------------------------------------------

        _update_stage(
            project_id,
            "technical_review",
            "running",
        )

        if mode in {
            "technical_review",
            "global",
        }:
            review_instruction = (
                instruction
            )
        else:
            review_instruction = (
                "Re-review the updated requirements, project "
                "plan, and architecture. Reflect the actual "
                "resulting artifacts and do not invent unrelated issues."
            )

        review = service.refine_review(
            requirements=requirements,
            project_plan=project_plan,
            architecture=architecture,
            current_review=review,
            instruction=review_instruction,
        )

        _update_artifact(
            project_id,
            "technical_review",
            review,
            instruction=review_instruction,
            source="refinement",
        )

        _update_stage(
            project_id,
            "technical_review",
            "completed",
        )

        project_store.update_project(
            project_id,
            status="completed",
            current_stage="completed",
            stage_status="completed",
            approved=(
                review.overall_status
                == "PASS"
            ),
            error=None,
        )

        project_store.add_event(
            project_id,
            "refinement_completed",
            message=(
                f"Refinement operation '{mode}' completed."
            ),
            data={
                "mode": mode,
                "instruction": instruction,
            },
        )

    except Exception as exc:

        project = project_store.get_project(
            project_id
        )

        current_stage = (
            project["current_stage"]
            if project
            else "unknown"
        )

        project_store.update_project(
            project_id,
            status="failed",
            stage_status="failed",
            error=str(exc),
        )

        project_store.add_event(
            project_id,
            "refinement_failed",
            stage=current_stage,
            message=str(exc),
            data={
                "mode": mode,
                "instruction": instruction,
            },
        )


# =========================================================
# Create
# =========================================================


@router.post(
    "",
    response_model=ProjectSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("analyst"))],
)
def create_project(
    request: ProjectCreateRequest,
    current_user: dict = Depends(get_current_user),
) -> ProjectSummary:

    idea = request.idea.strip()

    if not idea:
        raise HTTPException(
            status_code=400,
            detail="Software idea cannot be empty.",
        )

    project = project_store.create_project(
        project_id=str(uuid4()),
        idea=idea,
        owner_id=current_user["user_id"],
    )

    return _build_summary(
        project
    )


# =========================================================
# List projects
# =========================================================


@router.get(
    "",
    response_model=list[ProjectSummary],
)
def list_projects(
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
) -> list[ProjectSummary]:

    projects = project_store.list_projects(
        limit=limit,
        user_id=current_user["user_id"],
        is_admin=current_user["role"] == "admin",
    )

    return [
        _build_summary(
            project
        )
        for project in projects
    ]


# =========================================================
# Run
# =========================================================


@router.post(
    "/{project_id}/run",
    response_model=ProjectRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_project_roles("analyst"))],
)
def run_project(
    project_id: str,
) -> ProjectRunResponse:

    project = _get_project(
        project_id
    )

    if project["status"] in {
        "queued",
        "running",
    }:
        raise HTTPException(
            status_code=409,
            detail=(
                "Another project operation "
                "is already running."
            ),
        )

    project = (
        project_store.reset_stage_statuses(
            project_id,
            STAGES,
            first_stage="requirements",
        )
    )

    _WORKFLOW_EXECUTOR.submit(
        _run_project_job,
        project_id,
    )

    return _build_run_response(
        project
    )


# =========================================================
# Individual artifact regeneration
# =========================================================


@router.post(
    "/{project_id}/artifacts/{stage}/regenerate",
    response_model=ProjectRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_stage_role())],
)
def regenerate_artifact(
    project_id: str,
    stage: str,
    request: RefinementRequest,
) -> ProjectRunResponse:

    normalized_stage = stage.strip().casefold()

    if normalized_stage == "review":
        normalized_stage = "technical_review"

    if normalized_stage not in STAGES:
        raise HTTPException(
            status_code=404,
            detail=(
                "Unknown artifact stage. "
                "Use requirements, project_plan, "
                "architecture, or review."
            ),
        )

    project = _get_project(
        project_id
    )

    if project["status"] in {
        "queued",
        "running",
    }:
        raise HTTPException(
            status_code=409,
            detail=(
                "Another project operation "
                "is already running."
            ),
        )

    instruction = (
        request.instruction.strip()
    )

    if not instruction:
        raise HTTPException(
            status_code=400,
            detail=(
                "Refinement instruction "
                "cannot be empty."
            ),
        )

    try:
        _load_artifact_models(
            project_id
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    _check_stage_dependencies(
        project_id,
        normalized_stage,
    )

    if normalized_stage == "requirements":
        affected = list(STAGES)

    elif normalized_stage == "project_plan":
        affected = [
            "project_plan",
            "architecture",
            "technical_review",
        ]

    elif normalized_stage == "architecture":
        affected = [
            "architecture",
            "technical_review",
        ]

    else:
        affected = [
            "technical_review",
        ]

    project = (
        project_store.reset_stage_statuses(
            project_id,
            affected,
            first_stage=normalized_stage,
        )
    )

    _WORKFLOW_EXECUTOR.submit(
        _run_refinement_job,
        project_id,
        normalized_stage,
        instruction,
    )

    return _build_run_response(
        project
    )


# =========================================================
# Global refinement
# =========================================================


@router.post(
    "/{project_id}/refine",
    response_model=ProjectRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_project_roles("analyst"))],
)
def refine_project(
    project_id: str,
    request: RefinementRequest,
) -> ProjectRunResponse:

    project = _get_project(
        project_id
    )

    if project["status"] in {
        "queued",
        "running",
    }:
        raise HTTPException(
            status_code=409,
            detail=(
                "Another project operation "
                "is already running."
            ),
        )

    instruction = (
        request.instruction.strip()
    )

    if not instruction:
        raise HTTPException(
            status_code=400,
            detail=(
                "Refinement instruction "
                "cannot be empty."
            ),
        )

    try:
        _load_artifact_models(
            project_id
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    project = (
        project_store.reset_stage_statuses(
            project_id,
            STAGES,
            first_stage="requirements",
        )
    )

    _WORKFLOW_EXECUTOR.submit(
        _run_refinement_job,
        project_id,
        "global",
        instruction,
    )

    return _build_run_response(
        project
    )


# =========================================================
# Get project
# =========================================================


@router.get(
    "/{project_id}",
    response_model=ProjectSummary,
    dependencies=[Depends(require_project_roles())],
)
def get_project(
    project_id: str,
) -> ProjectSummary:

    project = _get_project(
        project_id
    )

    return _build_summary(
        project
    )


# =========================================================
# Get artifacts
# =========================================================


@router.get(
    "/{project_id}/artifacts",
    response_model=ProjectArtifactResponse,
    dependencies=[Depends(require_project_roles())],
)
def get_project_artifacts(
    project_id: str,
) -> ProjectArtifactResponse:

    project = _get_project(
        project_id
    )

    return _build_artifacts(
        project
    )


# =========================================================
# Version history
# =========================================================


@router.get(
    "/{project_id}/versions",
    response_model=dict[str, list[ProjectVersionResponse]],
    dependencies=[Depends(require_project_roles())],
)
def get_project_versions(
    project_id: str,
):

    _get_project(
        project_id
    )

    versions = (
        project_store.get_all_versions(
            project_id
        )
    )

    return {
        stage: [
            ProjectVersionResponse(
                artifact_version_id=item[
                    "artifact_version_id"
                ],
                project_id=item[
                    "project_id"
                ],
                stage=item["stage"],
                version_number=item[
                    "version_number"
                ],
                content=item["content"],
                instruction=item[
                    "instruction"
                ],
                source=item["source"],
                created_at=_to_datetime(
                    item["created_at"]
                ),
            )
            for item in stage_versions
        ]
        for stage, stage_versions
        in versions.items()
    }


# =========================================================
# Event history
# =========================================================


@router.get(
    "/{project_id}/events",
    response_model=list[ProjectEventResponse],
    dependencies=[Depends(require_project_roles())],
)
def get_project_events(
    project_id: str,
    limit: int = 100,
):

    _get_project(
        project_id
    )

    events = project_store.get_events(
        project_id,
        limit=limit,
    )

    return [
        ProjectEventResponse(
            event_id=item["event_id"],
            project_id=item["project_id"],
            event_type=item[
                "event_type"
            ],
            stage=item["stage"],
            message=item["message"],
            data=item["data"],
            created_at=_to_datetime(
                item["created_at"]
            ),
        )
        for item in events
    ]


# =========================================================
# Delete
# =========================================================


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_project_roles("owner"))],
)
def delete_project(
    project_id: str,
) -> None:

    _get_project(
        project_id
    )

    project_store.delete_project(
        project_id
    )


# =========================================================
# Backward-compatible synchronous endpoint
# =========================================================


@router.post(
    "/analyze",
    response_model=ProjectAnalysisResponse,
    dependencies=[Depends(require_roles("analyst"))],
)
def analyze_project(
    request: ProjectAnalysisRequest,
    current_user: dict = Depends(get_current_user),
) -> ProjectAnalysisResponse:

    idea = request.idea.strip()

    if not idea:
        raise HTTPException(
            status_code=400,
            detail="Software idea cannot be empty.",
        )

    project_id = str(uuid4())

    project_store.create_project(
        project_id=project_id,
        idea=idea,
        owner_id=current_user["user_id"],
    )

    try:
        workflow = ProjectWorkflow()

        result = workflow.run(
            idea,
            on_stage=lambda stage, stage_status: (
                _update_stage(
                    project_id,
                    stage,
                    stage_status,
                )
            ),
            on_artifact=lambda stage, artifact: (
                _update_artifact(
                    project_id,
                    stage,
                    artifact,
                    source="analysis",
                )
            ),
        )

        _update_artifact(
            project_id,
            "requirements",
            result.requirements,
            source="analysis",
        )

        _update_artifact(
            project_id,
            "project_plan",
            result.project_plan,
            source="analysis",
        )

        _update_artifact(
            project_id,
            "architecture",
            result.architecture,
            source="analysis",
        )

        _update_artifact(
            project_id,
            "technical_review",
            result.review,
            source="analysis",
        )

        project_store.update_project(
            project_id,
            project_name=(
                result.requirements.project_name
            ),
            status="completed",
            current_stage="completed",
            stage_status="completed",
            approved=result.approved,
            error=None,
        )

        artifacts = project_store.get_artifacts(
            project_id
        )

        return ProjectAnalysisResponse(
            project_id=project_id,
            project_name=(
                result.requirements.project_name
            ),
            status="completed",
            approved=result.approved,
            requirements=artifacts[
                "requirements"
            ],
            project_plan=artifacts[
                "project_plan"
            ],
            architecture=artifacts[
                "architecture"
            ],
            review=artifacts["technical_review"],
        )

    except ValueError as exc:

        project_store.update_project(
            project_id,
            status="failed",
            stage_status="failed",
            error=str(exc),
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except AgentExecutionError as exc:

        project_store.update_project(
            project_id,
            status="failed",
            stage_status="failed",
            error=str(exc),
        )

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        project_store.update_project(
            project_id,
            status="failed",
            stage_status="failed",
            error=str(exc),
        )

        raise HTTPException(
            status_code=500,
            detail="Unexpected project analysis error.",
        ) from exc


# =========================================================
# Project team membership
# =========================================================


@router.get(
    "/{project_id}/members",
    dependencies=[Depends(require_project_roles())],
)
def list_project_members(project_id: str) -> dict:
    _get_project(project_id)
    return {"members": auth_store.list_project_members(project_id)}


@router.post(
    "/{project_id}/members",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_project_roles("owner"))],
)
def add_project_member(
    project_id: str,
    request: ProjectMemberRequest,
) -> dict:
    _get_project(project_id)
    try:
        member = auth_store.add_project_member(
            project_id=project_id,
            email=str(request.email),
            role=request.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"member": member}


@router.delete(
    "/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_project_roles("owner"))],
)
def remove_project_member(project_id: str, user_id: str) -> None:
    _get_project(project_id)
    if not auth_store.remove_project_member(project_id, user_id):
        raise HTTPException(status_code=404, detail="Project member not found.")
