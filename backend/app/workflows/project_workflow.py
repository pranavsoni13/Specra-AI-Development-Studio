from dataclasses import dataclass
from typing import Any, Callable

from app.agents.requirement_analyst.agent import RequirementAnalyst
from app.agents.requirement_analyst.schemas import RequirementAnalysis

from app.agents.project_planner.agent import ProjectPlanner
from app.agents.project_planner.schemas import ProjectPlan

from app.agents.software_architect.agent import SoftwareArchitect
from app.agents.software_architect.schemas import SystemArchitecture

from app.agents.technical_reviewer.agent import TechnicalReviewer
from app.agents.technical_reviewer.schemas import ReviewReport


StageCallback = Callable[[str, str], None]
ArtifactCallback = Callable[[str, Any], None]


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

    Stage callbacks expose live progress.
    Artifact callbacks publish each completed artifact immediately.
    """

    def __init__(
        self,
        requirement_model: str | None = None,
        planner_model: str | None = None,
        architect_model: str | None = None,
        reviewer_model: str | None = None,
    ):
        requirement_kwargs = {}

        if requirement_model is not None:
            requirement_kwargs["model_name"] = requirement_model

        planner_kwargs = {}

        if planner_model is not None:
            planner_kwargs["model_name"] = planner_model

        architect_kwargs = {}

        if architect_model is not None:
            architect_kwargs["model_name"] = architect_model

        reviewer_kwargs = {}

        if reviewer_model is not None:
            reviewer_kwargs["model_name"] = reviewer_model

        self.requirement_agent = RequirementAnalyst(
            **requirement_kwargs
        )

        self.planner_agent = ProjectPlanner(
            **planner_kwargs
        )

        self.architect_agent = SoftwareArchitect(
            **architect_kwargs
        )

        self.reviewer_agent = TechnicalReviewer(
            **reviewer_kwargs
        )

    @staticmethod
    def _emit_stage(
        callback: StageCallback | None,
        stage: str,
        status: str,
    ) -> None:
        if callback is not None:
            callback(stage, status)

    @staticmethod
    def _emit_artifact(
        callback: ArtifactCallback | None,
        stage: str,
        artifact: Any,
    ) -> None:
        if callback is not None:
            callback(stage, artifact)

    def run(
        self,
        idea: str,
        on_stage: StageCallback | None = None,
        on_artifact: ArtifactCallback | None = None,
        project_context: str | None = None,
    ) -> ProjectWorkflowResult:

        if not idea or not idea.strip():
            raise ValueError(
                "Software idea cannot be empty."
            )

        cleaned_idea = idea.strip()

        # -------------------------------------------------
        # REQUIREMENTS
        # -------------------------------------------------

        self._emit_stage(
            on_stage,
            "requirements",
            "running",
        )

        try:
            if project_context and project_context.strip():
                requirements = self.requirement_agent.analyze(
                    cleaned_idea,
                    project_context=project_context,
                )
            else:
                requirements = self.requirement_agent.analyze(
                    cleaned_idea
                )
        except Exception:
            self._emit_stage(
                on_stage,
                "requirements",
                "failed",
            )
            raise

        self._emit_stage(
            on_stage,
            "requirements",
            "completed",
        )

        self._emit_artifact(
            on_artifact,
            "requirements",
            requirements,
        )

        # -------------------------------------------------
        # PROJECT PLAN
        # -------------------------------------------------

        self._emit_stage(
            on_stage,
            "project_plan",
            "running",
        )

        try:
            project_plan = self.planner_agent.plan(
                requirements
            )
        except Exception:
            self._emit_stage(
                on_stage,
                "project_plan",
                "failed",
            )
            raise

        self._emit_stage(
            on_stage,
            "project_plan",
            "completed",
        )

        self._emit_artifact(
            on_artifact,
            "project_plan",
            project_plan,
        )

        # -------------------------------------------------
        # ARCHITECTURE
        # -------------------------------------------------

        self._emit_stage(
            on_stage,
            "architecture",
            "running",
        )

        try:
            architecture = self.architect_agent.design(
                requirements,
                project_plan,
            )
        except Exception:
            self._emit_stage(
                on_stage,
                "architecture",
                "failed",
            )
            raise

        self._emit_stage(
            on_stage,
            "architecture",
            "completed",
        )

        self._emit_artifact(
            on_artifact,
            "architecture",
            architecture,
        )

        # -------------------------------------------------
        # TECHNICAL REVIEW
        # -------------------------------------------------

        self._emit_stage(
            on_stage,
            "technical_review",
            "running",
        )

        try:
            review = self.reviewer_agent.review(
                requirements,
                project_plan,
                architecture,
            )
        except Exception:
            self._emit_stage(
                on_stage,
                "technical_review",
                "failed",
            )
            raise

        self._emit_stage(
            on_stage,
            "technical_review",
            "completed",
        )

        self._emit_artifact(
            on_artifact,
            "technical_review",
            review,
        )

        return ProjectWorkflowResult(
            requirements=requirements,
            project_plan=project_plan,
            architecture=architecture,
            review=review,
        )