from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.requirement_analyst.agent import RequirementAnalyst
from app.agents.requirement_analyst.schemas import RequirementAnalysis
from app.core.errors.exceptions import AgentExecutionError


router = APIRouter(
    prefix="/api/v1/requirements",
    tags=["Requirements"],
)

requirement_analyst = RequirementAnalyst()


class RequirementAnalysisRequest(BaseModel):
    idea: str = Field(
        min_length=1,
        description="The user's raw software idea",
    )


@router.post(
    "/analyze",
    response_model=RequirementAnalysis,
)
def analyze_requirements(
    request: RequirementAnalysisRequest,
):
    try:
        return requirement_analyst.analyze(
            request.idea
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

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Unexpected requirement analysis error.",
        ) from exc