from fastapi import APIRouter, HTTPException

from app.core.quality_lab import evaluate_blueprint_quality
from app.core.storage.project_store import project_store


router = APIRouter(
    prefix="/api/v1/projects/{project_id}/quality",
    tags=["Blueprint Quality Lab"],
)


@router.get("")
def run_blueprint_quality_checks(project_id: str) -> dict:
    project = project_store.get_project(project_id)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{project_id}' not found.",
        )
    artifacts = project_store.get_artifacts(project_id)
    return evaluate_blueprint_quality(project_id, project, artifacts)
