from types import SimpleNamespace
from unittest.mock import patch

from app.workflows.project_workflow import ProjectWorkflow


def test_langgraph_runs_existing_agents_in_order_and_preserves_callbacks():
    with (
        patch("app.workflows.project_workflow.RequirementAnalyst"),
        patch("app.workflows.project_workflow.ProjectPlanner"),
        patch("app.workflows.project_workflow.SoftwareArchitect"),
        patch("app.workflows.project_workflow.TechnicalReviewer"),
    ):
        workflow = ProjectWorkflow()

    requirements = object()
    plan = object()
    architecture = object()
    review = SimpleNamespace(overall_status="PASS", model_dump=lambda: {})

    workflow.requirement_agent.analyze = lambda idea, **kwargs: requirements
    workflow.planner_agent.plan = lambda value: plan
    workflow.architect_agent.design = lambda req, project_plan: architecture
    workflow.reviewer_agent.review = (
        lambda req, project_plan, system_architecture: review
    )

    stages = []
    artifacts = []
    result = workflow.run(
        "  Build Specra tests  ",
        on_stage=lambda stage, status: stages.append((stage, status)),
        on_artifact=lambda stage, artifact: artifacts.append((stage, artifact)),
    )

    assert result.requirements is requirements
    assert result.project_plan is plan
    assert result.architecture is architecture
    assert result.review is review
    assert result.approved is True
    assert stages == [
        ("requirements", "running"),
        ("requirements", "completed"),
        ("project_plan", "running"),
        ("project_plan", "completed"),
        ("architecture", "running"),
        ("architecture", "completed"),
        ("technical_review", "running"),
        ("technical_review", "completed"),
    ]
    assert [stage for stage, _ in artifacts] == [
        "requirements",
        "project_plan",
        "architecture",
        "technical_review",
    ]


def test_langgraph_stops_after_agent_failure_and_emits_failed_status():
    with (
        patch("app.workflows.project_workflow.RequirementAnalyst"),
        patch("app.workflows.project_workflow.ProjectPlanner"),
        patch("app.workflows.project_workflow.SoftwareArchitect"),
        patch("app.workflows.project_workflow.TechnicalReviewer"),
    ):
        workflow = ProjectWorkflow()

    def fail_analysis(idea, **kwargs):
        raise RuntimeError("mock analysis failure")

    workflow.requirement_agent.analyze = fail_analysis
    stages = []

    try:
        workflow.run(
            "Build a test application",
            on_stage=lambda stage, status: stages.append((stage, status)),
        )
    except RuntimeError as exc:
        assert "mock analysis failure" in str(exc)
    else:
        raise AssertionError("Expected the workflow to propagate the node failure")

    assert stages == [
        ("requirements", "running"),
        ("requirements", "failed"),
    ]


def test_langgraph_rejects_empty_idea_before_invoking_nodes():
    with (
        patch("app.workflows.project_workflow.RequirementAnalyst"),
        patch("app.workflows.project_workflow.ProjectPlanner"),
        patch("app.workflows.project_workflow.SoftwareArchitect"),
        patch("app.workflows.project_workflow.TechnicalReviewer"),
    ):
        workflow = ProjectWorkflow()

    try:
        workflow.run("   ")
    except ValueError as exc:
        assert "cannot be empty" in str(exc)
    else:
        raise AssertionError("Expected empty software idea to be rejected")
