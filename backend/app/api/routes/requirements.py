from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.requirement_analyst.agent import RequirementAnalyst
from app.agents.requirement_analyst.schemas import RequirementAnalysis


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
async def analyze_requirements(
    request: RequirementAnalysisRequest,
):
    try:
        result = requirement_analyst.analyze(
            request.idea
        )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc