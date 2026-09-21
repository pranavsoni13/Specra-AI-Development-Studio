from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.project_planner.agent import ProjectPlanner
from app.agents.project_planner.schemas import ProjectPlan
from app.agents.requirement_analyst.schemas import RequirementAnalysis
from app.core.errors.exceptions import AgentExecutionError


router = APIRouter(
    prefix="/api/v1/planner",
    tags=["Project Planner"],
)

project_planner = ProjectPlanner()


class ProjectPlanRequest(BaseModel):
    requirements: RequirementAnalysis


@router.post(
    "/create",
    response_model=ProjectPlan,
)
def create_project_plan(
    request: ProjectPlanRequest,
):
    try:
        return project_planner.plan(
            request.requirements
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except TypeError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except AgentExecutionError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Unexpected project planning error.",
        ) from exc