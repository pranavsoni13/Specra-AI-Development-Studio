import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.testing_agent.agent import TestingAgent
from app.agents.testing_agent.schemas import TestResultUpdate
from app.core.security import (
    auth_store,
    get_current_user,
    require_project_roles,
)
from app.core.storage.project_store import project_store
from app.core.testing_store import test_store


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/tests",
    tags=["Testing Workspace"],
    dependencies=[Depends(get_current_user)],
)


def _project_or_404(project_id: str) -> dict:
    project = project_store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@router.get(
    "",
    dependencies=[Depends(require_project_roles())],
)
def get_test_suite(project_id: str, user: dict = Depends(get_current_user)) -> dict:
    _project_or_404(project_id)
    return {
        "suite": test_store.get_suite(project_id),
        "history": test_store.list_history(project_id),
        "my_role": auth_store.get_project_role(project_id, user),
    }


@router.post(
    "/generate",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_project_roles("analyst", "tester", "developer"))],
)
def generate_test_suite(project_id: str) -> dict:
    project = _project_or_404(project_id)
    artifacts = project_store.get_artifacts(project_id)
    requirements = artifacts.get("requirements")
    if not requirements:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Generate and save the requirements artifact before creating test cases.",
        )
    try:
        suite = TestingAgent().generate(
            requirements=requirements,
            project_plan=artifacts.get("project_plan"),
            architecture=artifacts.get("architecture"),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception(
            "Test-suite generation failed for project %s (%s)",
            project_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI test-design agent could not generate a valid suite. Check provider availability and try again.",
        ) from exc

    saved = test_store.save_suite(
        project_id=project_id,
        suite=suite.model_dump(),
        generation_model=TestingAgent.__init__.__defaults__[0]
        if TestingAgent.__init__.__defaults__
        else None,
    )
    return {"suite": saved, "project_status": project.get("status")}


@router.patch(
    "/cases/{test_id}/result",
    dependencies=[Depends(require_project_roles("tester", "developer"))],
)
def update_test_result(
    project_id: str,
    test_id: str,
    request: TestResultUpdate,
    user: dict = Depends(get_current_user),
) -> dict:
    _project_or_404(project_id)
    try:
        suite = test_store.update_result(
            project_id=project_id,
            test_id=test_id,
            status=request.status,
            execution_notes=request.execution_notes,
            environment=request.environment,
            executed_by=user["email"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if suite is None:
        raise HTTPException(
            status_code=404,
            detail="Test suite or test case not found. Generate a suite first.",
        )
    return {"suite": suite}


@router.get(
    "/history",
    dependencies=[Depends(require_project_roles())],
)
def get_test_history(project_id: str) -> dict:
    _project_or_404(project_id)
    return {"history": test_store.list_history(project_id)}
