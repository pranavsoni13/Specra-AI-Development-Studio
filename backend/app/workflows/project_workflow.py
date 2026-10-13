from dataclasses import dataclass
from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

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

        self.graph = self._build_graph()

    def _build_graph(self):
        """Compile the existing agent sequence as an explicit LangGraph graph."""
        graph = StateGraph(ProjectState)
        graph.add_node("requirements", self._requirements_node)
        graph.add_node("project_plan", self._project_plan_node)
        graph.add_node("architecture", self._architecture_node)
        graph.add_node("technical_review", self._technical_review_node)

        graph.add_edge(START, "requirements")
        graph.add_edge("requirements", "project_plan")
        graph.add_edge("project_plan", "architecture")
        graph.add_edge("architecture", "technical_review")
        graph.add_edge("technical_review", END)
        return graph.compile()

    def _requirements_node(self, state: ProjectState) -> dict:
        callback = state.get("on_stage")
        self._emit_stage(callback, "requirements", "running")
        try:
            context = state.get("project_context")
            if context and context.strip():
                artifact = self.requirement_agent.analyze(
                    state["idea"],
                    project_context=context,
                )
            else:
                artifact = self.requirement_agent.analyze(state["idea"])
        except Exception:
            self._emit_stage(callback, "requirements", "failed")
            raise

        self._emit_stage(callback, "requirements", "completed")
        self._emit_artifact(state.get("on_artifact"), "requirements", artifact)
        return {"requirements": artifact}

    def _project_plan_node(self, state: ProjectState) -> dict:
        callback = state.get("on_stage")
        self._emit_stage(callback, "project_plan", "running")
        try:
            artifact = self.planner_agent.plan(state["requirements"])
        except Exception:
            self._emit_stage(callback, "project_plan", "failed")
            raise

        self._emit_stage(callback, "project_plan", "completed")
        self._emit_artifact(state.get("on_artifact"), "project_plan", artifact)
        return {"project_plan": artifact}

    def _architecture_node(self, state: ProjectState) -> dict:
        callback = state.get("on_stage")
        self._emit_stage(callback, "architecture", "running")
        try:
            artifact = self.architect_agent.design(
                state["requirements"],
                state["project_plan"],
            )
        except Exception:
            self._emit_stage(callback, "architecture", "failed")
            raise

        self._emit_stage(callback, "architecture", "completed")
        self._emit_artifact(state.get("on_artifact"), "architecture", artifact)
        return {"architecture": artifact}

    def _technical_review_node(self, state: ProjectState) -> dict:
        callback = state.get("on_stage")
        self._emit_stage(callback, "technical_review", "running")
        try:
            artifact = self.reviewer_agent.review(
                state["requirements"],
                state["project_plan"],
                state["architecture"],
            )
        except Exception:
            self._emit_stage(callback, "technical_review", "failed")
            raise

        self._emit_stage(callback, "technical_review", "completed")
        self._emit_artifact(
            state.get("on_artifact"),
            "technical_review",
            artifact,
        )
        return {"review": artifact}

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

        state = self.graph.invoke(
            {
                "idea": cleaned_idea,
                "project_context": project_context,
                "on_stage": on_stage,
                "on_artifact": on_artifact,
            }
        )

        return ProjectWorkflowResult(
            requirements=state["requirements"],
            project_plan=state["project_plan"],
            architecture=state["architecture"],
            review=state["review"],
        )