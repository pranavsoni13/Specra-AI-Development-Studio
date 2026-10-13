from typing import Any, Callable, TypedDict

from app.agents.project_planner.schemas import ProjectPlan
from app.agents.requirement_analyst.schemas import RequirementAnalysis
from app.agents.software_architect.schemas import SystemArchitecture
from app.agents.technical_reviewer.schemas import ReviewReport


class ProjectState(TypedDict, total=False):
    idea: str
    project_context: str | None
    on_stage: Callable[[str, str], None] | None
    on_artifact: Callable[[str, Any], None] | None
    requirements: RequirementAnalysis
    project_plan: ProjectPlan
    architecture: SystemArchitecture
    review: ReviewReport
    errors: list[str]