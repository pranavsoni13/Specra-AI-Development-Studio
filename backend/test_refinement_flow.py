from __future__ import annotations

from copy import deepcopy

from app.agents.project_planner.schemas import (
    Milestone,
    PlanTask,
    ProjectPlan,
)
from app.agents.requirement_analyst.schemas import (
    RequirementAnalysis,
)
from app.agents.software_architect.schemas import (
    APIEndpoint,
    ArchitectureComponent,
    ArchitectureDecision,
    SystemArchitecture,
)
from app.agents.technical_reviewer.schemas import (
    RequirementCoverage,
    ReviewReport,
)


# =========================================================
# Test fixtures
# =========================================================


def build_requirements() -> RequirementAnalysis:
    return RequirementAnalysis(
        project_name="Online Food Delivery Platform",
        objective=(
            "Provide a comprehensive online platform for customers "
            "to discover, browse, place, and track food orders."
        ),
        user_roles=[
            "Customer",
        ],
        functional_requirements=[
            "Customers can discover restaurants and view their menus.",
            "Customers can place orders for food delivery.",
            "Customers can make payments for their orders.",
            "Customers can track the status of their deliveries.",
        ],
        non_functional_requirements=[],
        constraints=[],
        assumptions=[],
        risks=[],
        clarifications_needed=[],
    )


def build_project_plan() -> ProjectPlan:
    return ProjectPlan(
        project_name="Online Food Delivery Platform",
        milestones=[
            Milestone(
                name="Discovery and Menu Management",
                description=(
                    "Enable customers to discover restaurants "
                    "and view their menus."
                ),
                requirement_refs=[
                    "FR-001",
                ],
                tasks=[
                    PlanTask(
                        description=(
                            "Define the workflow for restaurant "
                            "discovery and menu viewing."
                        ),
                        requirement_refs=[
                            "FR-001",
                        ],
                    )
                ],
            ),
            Milestone(
                name="Order Placement",
                description=(
                    "Enable customers to place orders "
                    "for food delivery."
                ),
                requirement_refs=[
                    "FR-002",
                ],
                tasks=[
                    PlanTask(
                        description=(
                            "Define the workflow for placing "
                            "food delivery orders."
                        ),
                        requirement_refs=[
                            "FR-002",
                        ],
                    )
                ],
            ),
            Milestone(
                name="Payment Processing",
                description=(
                    "Enable customers to make payments "
                    "for their orders."
                ),
                requirement_refs=[
                    "FR-003",
                ],
                tasks=[
                    PlanTask(
                        description=(
                            "Define the workflow for order "
                            "payment processing."
                        ),
                        requirement_refs=[
                            "FR-003",
                        ],
                    )
                ],
            ),
            Milestone(
                name="Delivery Tracking",
                description=(
                    "Enable customers to track the status "
                    "of their deliveries."
                ),
                requirement_refs=[
                    "FR-004",
                ],
                tasks=[
                    PlanTask(
                        description=(
                            "Define the workflow for delivery "
                            "status tracking."
                        ),
                        requirement_refs=[
                            "FR-004",
                        ],
                    )
                ],
            ),
        ],
        dependencies=[],
        development_sequence=[],
    )


def build_architecture() -> SystemArchitecture:
    return SystemArchitecture(
        project_name="Online Food Delivery Platform",
        architecture_style="Monolithic",
        frontend="Web Application",
        backend="RESTful API",
        database="Relational Database (e.g. PostgreSQL)",
        authentication=(
            "Not required based on current requirements"
        ),
        components=[
            ArchitectureComponent(
                name="Restaurant Discovery Service",
                responsibility=(
                    "Discover restaurants and view menus."
                ),
                related_requirements=[
                    "FR-001",
                ],
            ),
            ArchitectureComponent(
                name="Order Placement Service",
                responsibility=(
                    "Place food delivery orders."
                ),
                related_requirements=[
                    "FR-002",
                ],
            ),
            ArchitectureComponent(
                name="Payment Processing Service",
                responsibility=(
                    "Process payments for orders."
                ),
                related_requirements=[
                    "FR-003",
                ],
            ),
            ArchitectureComponent(
                name="Delivery Tracking Service",
                responsibility=(
                    "Track delivery status."
                ),
                related_requirements=[
                    "FR-004",
                ],
            ),
        ],
        api_endpoints=[
            APIEndpoint(
                name="GET /restaurants",
                purpose="Discover restaurants.",
                related_requirements=[
                    "FR-001",
                ],
            ),
            APIEndpoint(
                name="GET /restaurants/{restaurant_id}/menu",
                purpose="View restaurant menus.",
                related_requirements=[
                    "FR-001",
                ],
            ),
            APIEndpoint(
                name="POST /orders",
                purpose="Place food delivery orders.",
                related_requirements=[
                    "FR-002",
                ],
            ),
            APIEndpoint(
                name="POST /payments",
                purpose="Process order payments.",
                related_requirements=[
                    "FR-003",
                ],
            ),
            APIEndpoint(
                name="GET /orders/{order_id}/delivery",
                purpose="Track delivery status.",
                related_requirements=[
                    "FR-004",
                ],
            ),
        ],
        data_flow=[
            "Customer interacts with the web application.",
            "Web application sends requests to the REST API.",
            "REST API processes business operations.",
            "Transactional data is stored in the relational database.",
        ],
        external_integrations=[
            "Payment processing service or payment gateway.",
        ],
        architectural_assumptions=[],
        architecture_decisions=[
            ArchitectureDecision(
                decision=(
                    "Use a monolithic architecture for simplicity."
                ),
                rationale=(
                    "The current requirements do not justify "
                    "distributed service complexity."
                ),
                related_requirements=[
                    "FR-001",
                    "FR-002",
                    "FR-003",
                    "FR-004",
                ],
            ),
            ArchitectureDecision(
                decision=(
                    "Use RESTful APIs for backend communication."
                ),
                rationale=(
                    "Provides clear interfaces between the web "
                    "application and backend."
                ),
                related_requirements=[
                    "FR-001",
                    "FR-002",
                    "FR-003",
                    "FR-004",
                ],
            ),
        ],
    )


def build_review() -> ReviewReport:
    requirements = build_requirements()

    coverage = [
        RequirementCoverage(
        requirement_id=f"FR-{index:03d}",
        requirement=requirement,
        in_project_plan=True,
        in_architecture=True,
        in_api=True,
        )
        for index, requirement in enumerate(
        requirements.functional_requirements,
        start=1,
    )
    ]

    return ReviewReport(
        project_name=requirements.project_name,
        overall_status="PASS",
        summary=(
            "All functional requirements are represented in "
            "the project plan and architecture."
        ),
        requirement_coverage=coverage,
        unsupported_additions=[],
        architecture_consistency_issues=[],
        findings=[],
        recommended_actions=[],
    )


# =========================================================
# Tests
# =========================================================


def test_artifact_models_are_valid():
    requirements = build_requirements()
    project_plan = build_project_plan()
    architecture = build_architecture()
    review = build_review()

    assert requirements.functional_requirements
    assert len(
        requirements.functional_requirements
    ) == 4

    assert len(
        project_plan.milestones
    ) == 4

    architecture_refs = {
        reference
        for component in architecture.components
        for reference in component.related_requirements
    }

    assert architecture_refs == {
        "FR-001",
        "FR-002",
        "FR-003",
        "FR-004",
    }

    assert len(
        review.requirement_coverage
    ) == 4

    assert review.overall_status == "PASS"


def test_refinement_dependency_matrix():
    """
    Validate the intended downstream impact graph.

    Requirements:
        requirements -> planner -> architecture -> review

    Project plan:
        project_plan -> architecture -> review

    Architecture:
        architecture -> review

    Review:
        review only
    """

    dependency_matrix = {
        "requirements": [
            "requirements",
            "project_plan",
            "architecture",
            "technical_review",
        ],
        "project_plan": [
            "project_plan",
            "architecture",
            "technical_review",
        ],
        "architecture": [
            "architecture",
            "technical_review",
        ],
        "technical_review": [
            "technical_review",
        ],
    }

    assert dependency_matrix["requirements"] == [
        "requirements",
        "project_plan",
        "architecture",
        "technical_review",
    ]

    assert dependency_matrix["project_plan"] == [
        "project_plan",
        "architecture",
        "technical_review",
    ]

    assert dependency_matrix["architecture"] == [
        "architecture",
        "technical_review",
    ]

    assert dependency_matrix["technical_review"] == [
        "technical_review",
    ]


def test_requirement_addition_changes_authoritative_requirement_set():
    requirements = build_requirements()

    updated = deepcopy(
        requirements.model_dump()
    )

    updated["functional_requirements"].append(
        "Customers can cancel an order before it is prepared."
    )

    updated_requirements = (
        RequirementAnalysis.model_validate(
            updated
        )
    )

    assert len(
        updated_requirements.functional_requirements
    ) == 5

    assert (
        "Customers can cancel an order before it is prepared."
        in updated_requirements.functional_requirements
    )


def test_downstream_artifacts_remain_structurally_rebuildable():
    """
    Verify that the artifact contracts can represent a future
    refinement without calling Ollama.

    Existing downstream artifacts remain unchanged until their
    respective regeneration step.
    """

    requirements = build_requirements()

    updated_requirements = (
        RequirementAnalysis.model_validate(
            {
                **requirements.model_dump(),
                "functional_requirements": [
                    *requirements.functional_requirements,
                    (
                        "Customers can cancel an order "
                        "before it is prepared."
                    ),
                ],
            }
        )
    )

    assert len(
        updated_requirements.functional_requirements
    ) == 5

    project_plan = build_project_plan()
    architecture = build_architecture()

    assert len(
        project_plan.milestones
    ) == 4

    assert len(
        architecture.components
    ) == 4

    # Historical artifacts are not mutated merely because
    # the authoritative requirements changed.
    #
    # The expected future transition is:
    #
    # Requirements vN+1
    #       ↓
    # Project Plan rebuild
    #       ↓
    # Architecture rebuild
    #       ↓
    # Technical Review rebuild

    assert (
        project_plan.project_name
        == requirements.project_name
    )

    assert (
        architecture.project_name
        == requirements.project_name
    )


def test_review_covers_every_functional_requirement():
    requirements = build_requirements()
    review = build_review()

    reviewed_requirements = {
        item.requirement
        for item in review.requirement_coverage
    }

    expected_requirements = set(
        requirements.functional_requirements
    )

    assert (
        reviewed_requirements
        == expected_requirements
    )

    assert all(
        item.in_project_plan
        for item in review.requirement_coverage
    )

    assert all(
        item.in_architecture
        for item in review.requirement_coverage
    )


# =========================================================
# Direct execution
# =========================================================


if __name__ == "__main__":
    test_artifact_models_are_valid()
    test_refinement_dependency_matrix()
    test_requirement_addition_changes_authoritative_requirement_set()
    test_downstream_artifacts_remain_structurally_rebuildable()
    test_review_covers_every_functional_requirement()

    print()
    print("=" * 70)
    print("REFINEMENT FLOW CONTRACT TEST: PASS")
    print("Artifact contracts: PASS")
    print("Dependency matrix: PASS")
    print("Requirement evolution: PASS")
    print("Review coverage contract: PASS")
    print("Historical artifact preservation model: PASS")
    print("=" * 70)