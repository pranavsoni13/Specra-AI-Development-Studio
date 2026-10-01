from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.errors.exceptions import AgentExecutionError
from app.workflows.project_workflow import ProjectWorkflow


router = APIRouter(
    prefix="/api/v1/projects",
    tags=["Projects"],
)


# ---------------------------------------------------------
# In-memory project storage for MVP
# ---------------------------------------------------------

_PROJECTS: dict[str, dict] = {}
_PROJECTS_LOCK = Lock()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------


class ProjectCreateRequest(BaseModel):
    idea: str = Field(
        min_length=1,
        description="The user's software idea or problem statement.",
    )


class ProjectSummary(BaseModel):
    project_id: str
    idea: str
    project_name: str | None = None
    status: str
    approved: bool | None = None
    created_at: datetime
    updated_at: datetime


class ProjectArtifactResponse(BaseModel):
    project_id: str
    project_name: str | None = None
    status: str
    approved: bool | None = None
    requirements: dict | None = None
    project_plan: dict | None = None
    architecture: dict | None = None
    review: dict | None = None
    created_at: datetime
    updated_at: datetime


class ProjectRunResponse(BaseModel):
    project_id: str
    project_name: str | None = None
    status: str
    approved: bool | None = None
    requirements: dict | None = None
    project_plan: dict | None = None
    architecture: dict | None = None
    review: dict | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class ProjectAnalysisRequest(BaseModel):
    idea: str = Field(
        min_length=1,
        description="The user's software idea or problem statement.",
    )


class ProjectAnalysisResponse(BaseModel):
    project_id: str
    project_name: str
    status: str
    approved: bool
    requirements: dict
    project_plan: dict
    architecture: dict
    review: dict


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------


def _get_project(project_id: str) -> dict:
    with _PROJECTS_LOCK:
        project = _PROJECTS.get(project_id)

        if project is None:
            raise HTTPException(
                status_code=404,
                detail=f"Project '{project_id}' not found.",
            )

        return project


def _artifact_dicts(result) -> dict:
    return {
        "requirements": result.requirements.model_dump(),
        "project_plan": result.project_plan.model_dump(),
        "architecture": result.architecture.model_dump(),
        "review": result.review.model_dump(),
    }


# ---------------------------------------------------------
# Create project
# ---------------------------------------------------------


@router.post(
    "",
    response_model=ProjectSummary,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    request: ProjectCreateRequest,
) -> ProjectSummary:

    idea = request.idea.strip()

    if not idea:
        raise HTTPException(
            status_code=400,
            detail="Software idea cannot be empty.",
        )

    project_id = str(uuid4())
    now = _utc_now()

    project = {
        "project_id": project_id,
        "idea": idea,
        "project_name": None,
        "status": "created",
        "approved": None,
        "requirements": None,
        "project_plan": None,
        "architecture": None,
        "review": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }

    with _PROJECTS_LOCK:
        _PROJECTS[project_id] = project

    return ProjectSummary(
        project_id=project["project_id"],
        idea=project["idea"],
        project_name=project["project_name"],
        status=project["status"],
        approved=project["approved"],
        created_at=project["created_at"],
        updated_at=project["updated_at"],
    )


# ---------------------------------------------------------
# Run complete workflow
# ---------------------------------------------------------


@router.post(
    "/{project_id}/run",
    response_model=ProjectRunResponse,
)
def run_project(
    project_id: str,
) -> ProjectRunResponse:

    project = _get_project(project_id)

    with _PROJECTS_LOCK:
        project["status"] = "running"
        project["error"] = None
        project["updated_at"] = _utc_now()

    try:
        workflow = ProjectWorkflow()

        result = workflow.run(
            project["idea"]
        )

        artifacts = _artifact_dicts(result)

        with _PROJECTS_LOCK:
            project["project_name"] = (
                result.requirements.project_name
            )
            project["requirements"] = artifacts["requirements"]
            project["project_plan"] = artifacts["project_plan"]
            project["architecture"] = artifacts["architecture"]
            project["review"] = artifacts["review"]
            project["approved"] = result.approved
            project["status"] = "completed"
            project["error"] = None
            project["updated_at"] = _utc_now()

        return ProjectRunResponse(
            project_id=project["project_id"],
            project_name=project["project_name"],
            status=project["status"],
            approved=project["approved"],
            requirements=project["requirements"],
            project_plan=project["project_plan"],
            architecture=project["architecture"],
            review=project["review"],
            error=None,
            created_at=project["created_at"],
            updated_at=project["updated_at"],
        )

    except ValueError as exc:
        with _PROJECTS_LOCK:
            project["status"] = "failed"
            project["error"] = str(exc)
            project["updated_at"] = _utc_now()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except AgentExecutionError as exc:
        with _PROJECTS_LOCK:
            project["status"] = "failed"
            project["error"] = str(exc)
            project["updated_at"] = _utc_now()

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        with _PROJECTS_LOCK:
            project["status"] = "failed"
            project["error"] = str(exc)
            project["updated_at"] = _utc_now()

        raise HTTPException(
            status_code=500,
            detail="Unexpected project workflow error.",
        ) from exc


# ---------------------------------------------------------
# Get project
# ---------------------------------------------------------


@router.get(
    "/{project_id}",
    response_model=ProjectSummary,
)
def get_project(
    project_id: str,
) -> ProjectSummary:

    project = _get_project(project_id)

    return ProjectSummary(
        project_id=project["project_id"],
        idea=project["idea"],
        project_name=project["project_name"],
        status=project["status"],
        approved=project["approved"],
        created_at=project["created_at"],
        updated_at=project["updated_at"],
    )


# ---------------------------------------------------------
# Get all artifacts
# ---------------------------------------------------------


@router.get(
    "/{project_id}/artifacts",
    response_model=ProjectArtifactResponse,
)
def get_project_artifacts(
    project_id: str,
) -> ProjectArtifactResponse:

    project = _get_project(project_id)

    return ProjectArtifactResponse(
        project_id=project["project_id"],
        project_name=project["project_name"],
        status=project["status"],
        approved=project["approved"],
        requirements=project["requirements"],
        project_plan=project["project_plan"],
        architecture=project["architecture"],
        review=project["review"],
        created_at=project["created_at"],
        updated_at=project["updated_at"],
    )


# ---------------------------------------------------------
# Backward-compatible one-shot analysis endpoint
# ---------------------------------------------------------


@router.post(
    "/analyze",
    response_model=ProjectAnalysisResponse,
)
def analyze_project(
    request: ProjectAnalysisRequest,
) -> ProjectAnalysisResponse:

    idea = request.idea.strip()

    if not idea:
        raise HTTPException(
            status_code=400,
            detail="Software idea cannot be empty.",
        )

    project_id = str(uuid4())
    now = _utc_now()

    project = {
        "project_id": project_id,
        "idea": idea,
        "project_name": None,
        "status": "running",
        "approved": None,
        "requirements": None,
        "project_plan": None,
        "architecture": None,
        "review": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }

    with _PROJECTS_LOCK:
        _PROJECTS[project_id] = project

    try:
        workflow = ProjectWorkflow()

        result = workflow.run(idea)

        artifacts = _artifact_dicts(result)

        with _PROJECTS_LOCK:
            project["project_name"] = (
                result.requirements.project_name
            )
            project["requirements"] = artifacts["requirements"]
            project["project_plan"] = artifacts["project_plan"]
            project["architecture"] = artifacts["architecture"]
            project["review"] = artifacts["review"]
            project["approved"] = result.approved
            project["status"] = "completed"
            project["error"] = None
            project["updated_at"] = _utc_now()

        return ProjectAnalysisResponse(
            project_id=project_id,
            project_name=result.requirements.project_name,
            status="completed",
            approved=result.approved,
            requirements=artifacts["requirements"],
            project_plan=artifacts["project_plan"],
            architecture=artifacts["architecture"],
            review=artifacts["review"],
        )

    except ValueError as exc:
        with _PROJECTS_LOCK:
            project["status"] = "failed"
            project["error"] = str(exc)
            project["updated_at"] = _utc_now()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except AgentExecutionError as exc:
        with _PROJECTS_LOCK:
            project["status"] = "failed"
            project["error"] = str(exc)
            project["updated_at"] = _utc_now()

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        with _PROJECTS_LOCK:
            project["status"] = "failed"
            project["error"] = str(exc)
            project["updated_at"] = _utc_now()

        raise HTTPException(
            status_code=500,
            detail="Unexpected project analysis error.",
        ) from exc