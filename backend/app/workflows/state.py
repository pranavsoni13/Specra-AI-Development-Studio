from collections.abc import Callable
from typing import Any, TypedDict

from app.agents.project_planner.schemas import ProjectPlan
from app.agents.requirement_analyst.schemas import RequirementAnalysis
from app.agents.software_architect.schemas import SystemArchitecture
from app.agents.technical_reviewer.schemas import ReviewReport


StageCallback = Callable[[str, str], None]
ArtifactCallback = Callable[[str, Any], None]


class ProjectState(TypedDict, total=False):
    """Typed state passed between Specra's LangGraph workflow nodes."""

    idea: str
    project_context: str | None
    requirements: RequirementAnalysis
    project_plan: ProjectPlan
    architecture: SystemArchitecture
    review: ReviewReport
    errors: list[str]
    on_stage: StageCallback | None
    on_artifact: ArtifactCallback | None
