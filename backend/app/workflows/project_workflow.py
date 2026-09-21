from langgraph.graph import END, START, StateGraph

from app.agents.project_planner.agent import ProjectPlanner
from app.agents.requirement_analyst.agent import RequirementAnalyst
from app.agents.software_architect.agent import SoftwareArchitect
from app.agents.technical_reviewer.agent import TechnicalReviewer

from .state import ProjectState


requirement_agent = RequirementAnalyst()
planner_agent = ProjectPlanner()
architect_agent = SoftwareArchitect()
reviewer_agent = TechnicalReviewer()


def analyze_requirements(
    state: ProjectState,
) -> ProjectState:
    idea = state.get("idea", "").strip()

    if not idea:
        raise ValueError(
            "Project idea cannot be empty."
        )

    requirements = requirement_agent.analyze(idea)

    return {
        **state,
        "requirements": requirements,
    }


def create_project_plan(
    state: ProjectState,
) -> ProjectState:
    requirements = state.get("requirements")

    if requirements is None:
        raise ValueError(
            "Requirement analysis is missing."
        )

    project_plan = planner_agent.plan(
        requirements
    )

    return {
        **state,
        "project_plan": project_plan,
    }


def create_architecture(
    state: ProjectState,
) -> ProjectState:
    requirements = state.get("requirements")
    project_plan = state.get("project_plan")

    if requirements is None:
        raise ValueError(
            "Requirement analysis is missing."
        )

    if project_plan is None:
        raise ValueError(
            "Project plan is missing."
        )

    architecture = architect_agent.design(
        requirements,
        project_plan,
    )

    return {
        **state,
        "architecture": architecture,
    }


def review_project(
    state: ProjectState,
) -> ProjectState:
    requirements = state.get("requirements")
    project_plan = state.get("project_plan")
    architecture = state.get("architecture")

    if requirements is None:
        raise ValueError(
            "Requirement analysis is missing."
        )

    if project_plan is None:
        raise ValueError(
            "Project plan is missing."
        )

    if architecture is None:
        raise ValueError(
            "System architecture is missing."
        )

    review = reviewer_agent.review(
        requirements,
        project_plan,
        architecture,
    )

    return {
        **state,
        "review": review,
    }


def build_project_workflow():
    graph = StateGraph(ProjectState)

    graph.add_node(
        "requirement_analysis",
        analyze_requirements,
    )

    graph.add_node(
        "project_planning",
        create_project_plan,
    )

    graph.add_node(
        "architecture_design",
        create_architecture,
    )

    graph.add_node(
        "technical_review",
        review_project,
    )

    graph.add_edge(
        START,
        "requirement_analysis",
    )

    graph.add_edge(
        "requirement_analysis",
        "project_planning",
    )

    graph.add_edge(
        "project_planning",
        "architecture_design",
    )

    graph.add_edge(
        "architecture_design",
        "technical_review",
    )

    graph.add_edge(
        "technical_review",
        END,
    )

    return graph.compile()


project_workflow = build_project_workflow()