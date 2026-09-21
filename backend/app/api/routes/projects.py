from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.project_planner.schemas import ProjectPlan
from app.agents.requirement_analyst.schemas import RequirementAnalysis
from app.agents.software_architect.schemas import SystemArchitecture
from app.agents.technical_reviewer.schemas import ReviewReport
from app.core.errors.exceptions import AgentExecutionError
from app.workflows.project_workflow import project_workflow


router = APIRouter(
    prefix="/api/v1/projects",
    tags=["Projects"],
)


class ProjectAnalysisRequest(BaseModel):
    idea: str = Field(
        min_length=1,
        description="The user's software idea or problem statement",
    )


class ProjectAnalysisResponse(BaseModel):
    requirements: RequirementAnalysis
    project_plan: ProjectPlan
    architecture: SystemArchitecture
    review: ReviewReport


@router.post(
    "/analyze",
    response_model=ProjectAnalysisResponse,
)
def analyze_project(
    request: ProjectAnalysisRequest,
):
    try:
        result = project_workflow.invoke(
            {
                "idea": request.idea,
            }
        )

        requirements = result.get("requirements")
        project_plan = result.get("project_plan")
        architecture = result.get("architecture")
        review = result.get("review")

        if requirements is None:
            raise RuntimeError(
                "Workflow completed without requirement analysis."
            )

        if project_plan is None:
            raise RuntimeError(
                "Workflow completed without project plan."
            )

        if architecture is None:
            raise RuntimeError(
                "Workflow completed without system architecture."
            )

        if review is None:
            raise RuntimeError(
                "Workflow completed without technical review."
            )

        return ProjectAnalysisResponse(
            requirements=requirements,
            project_plan=project_plan,
            architecture=architecture,
            review=review,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except AgentExecutionError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Unexpected project analysis error.",
        ) from exc