from dataclasses import dataclass

from app.agents.requirement_analyst.agent import RequirementAnalyst
from app.agents.requirement_analyst.schemas import RequirementAnalysis

from app.agents.project_planner.agent import ProjectPlanner
from app.agents.project_planner.schemas import ProjectPlan

from app.agents.software_architect.agent import SoftwareArchitect
from app.agents.software_architect.schemas import SystemArchitecture

from app.agents.technical_reviewer.agent import TechnicalReviewer
from app.agents.technical_reviewer.schemas import ReviewReport

from app.core.model_config import (
    REQUIREMENT_ANALYST_MODEL,
    PROJECT_PLANNER_MODEL,
    SOFTWARE_ARCHITECT_MODEL,
    TECHNICAL_REVIEWER_MODEL,
)


@dataclass
class ProjectWorkflowResult:
    requirements: RequirementAnalysis
    project_plan: ProjectPlan
    architecture: SystemArchitecture
    review: ReviewReport

    @property
    def approved(self) -> bool:
        return self.review.overall_status == "PASS"

    def to_dict(self) -> dict:
        return {
            "requirements": self.requirements.model_dump(),
            "project_plan": self.project_plan.model_dump(),
            "architecture": self.architecture.model_dump(),
            "review": self.review.model_dump(),
            "approved": self.approved,
        }


class ProjectWorkflow:
    """
    End-to-end AI Development Studio workflow.

    Idea
      -> Requirement Analysis
      -> Project Plan
      -> System Architecture
      -> Technical Review
    """

    def __init__(
        self,
        requirement_model: str = REQUIREMENT_ANALYST_MODEL,
        planner_model: str = PROJECT_PLANNER_MODEL,
        architect_model: str = SOFTWARE_ARCHITECT_MODEL,
        reviewer_model: str = TECHNICAL_REVIEWER_MODEL,
    ):
        self.requirement_agent = RequirementAnalyst(
            model_name=requirement_model
        )

        self.planner_agent = ProjectPlanner(
            model_name=planner_model
        )

        self.architect_agent = SoftwareArchitect(
            model_name=architect_model
        )

        self.reviewer_agent = TechnicalReviewer(
            model_name=reviewer_model
        )

    def run(self, idea: str) -> ProjectWorkflowResult:
        if not idea or not idea.strip():
            raise ValueError(
                "Software idea cannot be empty."
            )

        cleaned_idea = idea.strip()

        print("\n=== WORKFLOW: REQUIREMENTS ===")
        requirements = self.requirement_agent.analyze(
            cleaned_idea
        )

        print("\n=== WORKFLOW: PROJECT PLAN ===")
        project_plan = self.planner_agent.plan(
            requirements
        )

        print("\n=== WORKFLOW: ARCHITECTURE ===")
        architecture = self.architect_agent.design(
            requirements,
            project_plan,
        )

        print("\n=== WORKFLOW: TECHNICAL REVIEW ===")
        review = self.reviewer_agent.review(
            requirements,
            project_plan,
            architecture,
        )

        return ProjectWorkflowResult(
            requirements=requirements,
            project_plan=project_plan,
            architecture=architecture,
            review=review,
        )