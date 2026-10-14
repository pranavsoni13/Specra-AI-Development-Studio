from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.project_planner.agent import ProjectPlanner
from app.agents.project_planner.schemas import ProjectPlan
from app.agents.requirement_analyst.agent import RequirementAnalyst
from app.agents.requirement_analyst.schemas import RequirementAnalysis
from app.agents.software_architect.agent import SoftwareArchitect
from app.agents.software_architect.schemas import SystemArchitecture
from app.agents.technical_reviewer.agent import TechnicalReviewer
from app.agents.technical_reviewer.schemas import ReviewReport
from app.workflows.state import ArtifactCallback, ProjectState, StageCallback


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
    End-to-end Specra workflow, orchestrated with LangGraph.

    Idea
      -> Requirement Analysis
      -> Project Plan
      -> System Architecture
      -> Technical Review

    Agent implementations, artifact schemas, stage names, and callbacks are
    intentionally preserved so this orchestration change stays backwards
    compatible with the existing API and frontend.
    """

    def __init__(
        self,
        requirement_model: str | None = None,
        planner_model: str | None = None,
        architect_model: str | None = None,
        reviewer_model: str | None = None,
    ):
        requirement_kwargs = (
            {"model_name": requirement_model}
            if requirement_model is not None
            else {}
        )
        planner_kwargs = (
            {"model_name": planner_model}
            if planner_model is not None
            else {}
        )
        architect_kwargs = (
            {"model_name": architect_model}
            if architect_model is not None
            else {}
        )
        reviewer_kwargs = (
            {"model_name": reviewer_model}
            if reviewer_model is not None
            else {}
        )

        self.requirement_agent = RequirementAnalyst(**requirement_kwargs)
        self.planner_agent = ProjectPlanner(**planner_kwargs)
        self.architect_agent = SoftwareArchitect(**architect_kwargs)
        self.reviewer_agent = TechnicalReviewer(**reviewer_kwargs)

        # Keep the initial graph deliberately linear. Conditional review loops
        # can be added later after their retry policy is covered by tests.
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
        self.workflow_graph = graph.compile()

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

    def _requirements_node(self, state: ProjectState) -> dict:
        stage_callback = state.get("on_stage")
        artifact_callback = state.get("on_artifact")
        self._emit_stage(stage_callback, "requirements", "running")
        try:
            context = state.get("project_context")
            if context and context.strip():
                result = self.requirement_agent.analyze(
                    state["idea"],
                    project_context=context,
                )
            else:
                result = self.requirement_agent.analyze(state["idea"])
        except Exception:
            self._emit_stage(stage_callback, "requirements", "failed")
            raise
        self._emit_stage(stage_callback, "requirements", "completed")
        self._emit_artifact(artifact_callback, "requirements", result)
        return {"requirements": result}

    def _project_plan_node(self, state: ProjectState) -> dict:
        stage_callback = state.get("on_stage")
        artifact_callback = state.get("on_artifact")
        self._emit_stage(stage_callback, "project_plan", "running")
        try:
            result = self.planner_agent.plan(state["requirements"])
        except Exception:
            self._emit_stage(stage_callback, "project_plan", "failed")
            raise
        self._emit_stage(stage_callback, "project_plan", "completed")
        self._emit_artifact(artifact_callback, "project_plan", result)
        return {"project_plan": result}

    def _architecture_node(self, state: ProjectState) -> dict:
        stage_callback = state.get("on_stage")
        artifact_callback = state.get("on_artifact")
        self._emit_stage(stage_callback, "architecture", "running")
        try:
            result = self.architect_agent.design(
                state["requirements"],
                state["project_plan"],
            )
        except Exception:
            self._emit_stage(stage_callback, "architecture", "failed")
            raise
        self._emit_stage(stage_callback, "architecture", "completed")
        self._emit_artifact(artifact_callback, "architecture", result)
        return {"architecture": result}

    def _technical_review_node(self, state: ProjectState) -> dict:
        stage_callback = state.get("on_stage")
        artifact_callback = state.get("on_artifact")
        self._emit_stage(stage_callback, "technical_review", "running")
        try:
            result = self.reviewer_agent.review(
                state["requirements"],
                state["project_plan"],
                state["architecture"],
            )
        except Exception:
            self._emit_stage(stage_callback, "technical_review", "failed")
            raise
        self._emit_stage(stage_callback, "technical_review", "completed")
        self._emit_artifact(artifact_callback, "technical_review", result)
        return {"review": result}

    def run(
        self,
        idea: str,
        on_stage: StageCallback | None = None,
        on_artifact: ArtifactCallback | None = None,
        project_context: str | None = None,
    ) -> ProjectWorkflowResult:
        if not idea or not idea.strip():
            raise ValueError("Software idea cannot be empty.")

        final_state = self.workflow_graph.invoke(
            {
                "idea": idea.strip(),
                "project_context": project_context,
                "on_stage": on_stage,
                "on_artifact": on_artifact,
            }
        )

        return ProjectWorkflowResult(
            requirements=final_state["requirements"],
            project_plan=final_state["project_plan"],
            architecture=final_state["architecture"],
            review=final_state["review"],
        )
