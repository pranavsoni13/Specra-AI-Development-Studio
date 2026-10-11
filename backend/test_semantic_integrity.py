from app.agents.project_planner.schemas import Milestone, PlanTask, ProjectPlan
from app.agents.requirement_analyst.schemas import RequirementAnalysis
from app.agents.software_architect.quality import ArchitectureQualityController
from app.agents.software_architect.schemas import (
    APIEndpoint,
    ArchitectureComponent,
    ArchitectureDecision,
    SystemArchitecture,
)
from app.agents.technical_reviewer.quality import TechnicalReviewQualityController
from app.agents.technical_reviewer.schemas import RequirementCoverage, ReviewReport
from app.core.traceability.requirements import RequirementRegistry
from app.core.traceability.requirement_polarity import (
    authentication_policy,
    contains_positive_authentication_mention,
)


REQUIREMENTS = RequirementAnalysis(
    project_name="Online Food Delivery Platform",
    objective="Enable customers to discover restaurants, browse menus, place orders, make payments, and track deliveries.",
    user_roles=["Customer"],
    functional_requirements=[
        "Customers can discover restaurants",
        "Customers can browse menus",
        "Customers can place orders",
        "Customers can make payments",
        "Customers can track deliveries",
    ],
    non_functional_requirements=[],
    constraints=[],
    assumptions=[],
    risks=[],
    clarifications_needed=[],
)


def build_plan() -> ProjectPlan:
    requirements = REQUIREMENTS.functional_requirements

    milestones = [
        Milestone(
            name="Discovery and Menu",
            description="Support restaurant discovery and menu browsing.",
            requirement_refs=["FR-001", "FR-002"],
            tasks=[
                PlanTask(
                    description="Define restaurant discovery workflow.",
                    requirement_refs=["FR-001"],
                ),
                PlanTask(
                    description="Define menu browsing workflow.",
                    requirement_refs=["FR-002"],
                ),
            ],
        ),
        Milestone(
            name="Orders and Payments",
            description="Support order placement and payment processing.",
            requirement_refs=["FR-003", "FR-004"],
            tasks=[
                PlanTask(
                    description="Define order placement workflow.",
                    requirement_refs=["FR-003"],
                ),
                PlanTask(
                    description="Define payment processing workflow.",
                    requirement_refs=["FR-004"],
                ),
            ],
        ),
        Milestone(
            name="Delivery Tracking",
            description="Support delivery tracking.",
            requirement_refs=["FR-005"],
            tasks=[
                PlanTask(
                    description="Define delivery tracking workflow.",
                    requirement_refs=["FR-005"],
                ),
            ],
        ),
    ]

    return ProjectPlan(
        project_name=REQUIREMENTS.project_name,
        milestones=milestones,
        dependencies=[],
        development_sequence=[milestone.name for milestone in milestones],
    )


def build_clean_architecture() -> SystemArchitecture:
    return SystemArchitecture(
        project_name=REQUIREMENTS.project_name,
        architecture_style="Modular Monolith",
        frontend="Web",
        backend="RESTful API",
        database="Relational Database",
        authentication="Not required based on current requirements",
        components=[
            ArchitectureComponent(
                name="Restaurant Discovery",
                responsibility="Supports restaurant discovery.",
                related_requirements=["FR-001"],
            ),
            ArchitectureComponent(
                name="Menu Browsing",
                responsibility="Supports menu browsing.",
                related_requirements=["FR-002"],
            ),
            ArchitectureComponent(
                name="Order Placement",
                responsibility="Supports order placement.",
                related_requirements=["FR-003"],
            ),
            ArchitectureComponent(
                name="Payment Processing",
                responsibility="Supports payment processing.",
                related_requirements=["FR-004"],
            ),
            ArchitectureComponent(
                name="Delivery Tracking",
                responsibility="Supports delivery tracking.",
                related_requirements=["FR-005"],
            ),
        ],
        api_endpoints=[
            APIEndpoint(
                name="GET /restaurants",
                purpose="Discover restaurants.",
                related_requirements=["FR-001"],
            ),
            APIEndpoint(
                name="GET /restaurants/{restaurant_id}/menu",
                purpose="Browse menus.",
                related_requirements=["FR-002"],
            ),
            APIEndpoint(
                name="POST /orders",
                purpose="Place orders.",
                related_requirements=["FR-003"],
            ),
            APIEndpoint(
                name="POST /payments",
                purpose="Process payments.",
                related_requirements=["FR-004"],
            ),
            APIEndpoint(
                name="GET /orders/{order_id}/delivery",
                purpose="Track deliveries.",
                related_requirements=["FR-005"],
            ),
        ],
        data_flow=[
            "Customer uses the frontend, which sends requests to the backend for the required application capabilities."
        ],
        external_integrations=[],
        architectural_assumptions=[],
        architecture_decisions=[
            ArchitectureDecision(
                decision="Use a modular monolith architecture.",
                rationale="The current scope does not justify the operational complexity of independently deployed services.",
                related_requirements=["FR-001", "FR-002", "FR-003", "FR-004", "FR-005"],
            ),
            ArchitectureDecision(
                decision="Use a relational database.",
                rationale="The application manages structured transactional data such as orders and payments.",
                related_requirements=["FR-003", "FR-004"],
            ),
        ],
    )


def build_bad_auth_architecture() -> SystemArchitecture:
    architecture = build_clean_architecture()
    architecture.architecture_decisions.append(
        ArchitectureDecision(
            decision="No authentication required.",
            rationale="Authentication is explicitly stated as unnecessary in the requirements.",
            related_requirements=["FR-001", "FR-002", "FR-003", "FR-004", "FR-005"],
        )
    )
    return architecture


def build_clean_review() -> ReviewReport:
    registry = RequirementRegistry.from_analysis(REQUIREMENTS)
    return ReviewReport(
        project_name=REQUIREMENTS.project_name,
        overall_status="PASS",
        summary="All functional requirements are covered in the project plan and architecture.",
        requirement_coverage=[
            RequirementCoverage(
                requirement_id=requirement_id,
                requirement=registry.text_for_id(requirement_id),
                in_project_plan=True,
                in_architecture=True,
                in_api=True,
            )
            for requirement_id in registry.ids
        ],
        unsupported_additions=[],
        architecture_consistency_issues=[],
        findings=[],
        recommended_actions=[],
    )


def test_architecture_quality_rejects_false_auth_provenance() -> None:
    controller = ArchitectureQualityController()
    bad = build_bad_auth_architecture()

    try:
        controller.validate(
            bad,
            REQUIREMENTS,
            build_plan(),
            RequirementRegistry.from_analysis(REQUIREMENTS),
        )
    except ValueError as exc:
        message = str(exc).casefold()
        assert "authentication" in message
        assert "unsupported" in message or "negative" in message
        return

    raise AssertionError(
        "ArchitectureQualityController accepted a false authentication provenance claim."
    )


def test_reviewer_flags_false_auth_provenance() -> None:
    controller = TechnicalReviewQualityController()
    bad_architecture = build_bad_auth_architecture()
    report = build_clean_review()

    validated = controller.validate(
        report=report,
        requirements=REQUIREMENTS,
        project_plan=build_plan(),
        architecture=bad_architecture,
        registry=RequirementRegistry.from_analysis(REQUIREMENTS),
    )

    assert validated.overall_status == "NEEDS_REVISION"
    assert any(
        "authentication provenance" in finding.title.casefold()
        for finding in validated.findings
    )
    assert validated.unsupported_additions
    assert validated.architecture_consistency_issues
    assert validated.recommended_actions


def test_clean_architecture_remains_valid() -> None:
    controller = ArchitectureQualityController()
    validated = controller.validate(
        build_clean_architecture(),
        REQUIREMENTS,
        build_plan(),
        RequirementRegistry.from_analysis(REQUIREMENTS),
    )

    assert validated.authentication == "Not required based on current requirements"
    assert set(
        reference
        for component in validated.components
        for reference in component.related_requirements
    ) == set(RequirementRegistry.from_analysis(REQUIREMENTS).ids)



def test_architect_accepts_explicitly_negated_tracking_mention() -> None:
    architecture = build_clean_architecture()
    architecture.architectural_assumptions = [
        "Real-time delivery updates are outside scope and will not be implemented."
    ]
    validated = ArchitectureQualityController().validate(
        architecture,
        REQUIREMENTS,
        build_plan(),
        RequirementRegistry.from_analysis(REQUIREMENTS),
    )
    assert validated.architectural_assumptions


def test_architect_rejects_positive_unsupported_tracking_capability() -> None:
    architecture = build_clean_architecture()
    architecture.data_flow.append(
        "Customer receives real-time delivery status updates."
    )
    try:
        ArchitectureQualityController().validate(
            architecture,
            REQUIREMENTS,
            build_plan(),
            RequirementRegistry.from_analysis(REQUIREMENTS),
        )
    except ValueError as exc:
        message = str(exc).casefold()
        assert "real-time" in message or "realtime" in message
        assert "data_flow" in message
        return
    raise AssertionError(
        "Architecture accepted positive real-time behavior absent from the requirements."
    )


def test_reviewer_does_not_flag_negated_tracking_mention() -> None:
    architecture = build_clean_architecture()
    architecture.architectural_assumptions = [
        "Real-time delivery updates are outside scope and will not be implemented."
    ]
    result = TechnicalReviewQualityController().validate(
        report=build_clean_review(),
        requirements=REQUIREMENTS,
        project_plan=build_plan(),
        architecture=architecture,
        registry=RequirementRegistry.from_analysis(REQUIREMENTS),
    )
    assert result.overall_status == "PASS"
    assert not any(
        "real-time" in finding.title.casefold()
        or "tracking" in finding.title.casefold()
        for finding in result.findings
    )


def test_reviewer_flags_positive_unsupported_tracking_capability() -> None:
    architecture = build_clean_architecture()
    architecture.data_flow.append(
        "Customer receives real-time delivery status updates."
    )
    result = TechnicalReviewQualityController().validate(
        report=build_clean_review(),
        requirements=REQUIREMENTS,
        project_plan=build_plan(),
        architecture=architecture,
        registry=RequirementRegistry.from_analysis(REQUIREMENTS),
    )
    assert result.overall_status == "NEEDS_REVISION"
    assert any(
        "unsupported real-time" in finding.title.casefold()
        for finding in result.findings
    )

def test_modal_tracking_assumption_is_reviewed_without_architect_retry() -> None:
    architecture = build_clean_architecture()
    architecture.architectural_assumptions = [
        "Delivery status updates may require real-time tracking mechanisms."
    ]
    validated_architecture = ArchitectureQualityController().validate(
        architecture,
        REQUIREMENTS,
        build_plan(),
        RequirementRegistry.from_analysis(REQUIREMENTS),
    )
    assert validated_architecture.architectural_assumptions

    report = TechnicalReviewQualityController().validate(
        report=build_clean_review(),
        requirements=REQUIREMENTS,
        project_plan=build_plan(),
        architecture=validated_architecture,
        registry=RequirementRegistry.from_analysis(REQUIREMENTS),
    )
    assert report.overall_status == "PASS"
    assert any(
        "speculative assumption" in finding.title.casefold()
        for finding in report.findings
    )
    assert report.recommended_actions


def test_explicit_no_auth_constraint_overrides_keyword_mentions() -> None:
    requirements = REQUIREMENTS.model_copy(
        update={
            "constraints": [
                "No authentication. Do not add an identity provider."
            ]
        }
    )
    required, prohibited = authentication_policy(requirements)
    assert required is False
    assert prohibited is True
    assert contains_positive_authentication_mention(
        "Use an identity provider for login."
    )
    assert not contains_positive_authentication_mention(
        "Do not add an identity provider."
    )

    architecture = build_clean_architecture()
    architecture.authentication = "Required based on RequirementAnalysis"
    try:
        ArchitectureQualityController._check_authentication_consistency(
            architecture,
            requirements,
        )
    except ValueError as exc:
        assert "prohibiting authentication" in str(exc).casefold()
    else:
        raise AssertionError(
            "Architecture accepted authentication although the scope explicitly prohibits it."
        )

    clean_auth = build_clean_architecture()
    clean_auth.authentication = "Not required based on current requirements"
    clean_auth.architectural_assumptions = [
        "Use an identity provider to manage user login."
    ]
    try:
        ArchitectureQualityController._check_authentication_consistency(
            clean_auth,
            requirements,
        )
    except ValueError as exc:
        assert "architectural_assumptions[0]" in str(exc).casefold()
    else:
        raise AssertionError(
            "Architecture accepted a positive identity-provider assumption despite an explicit prohibition."
        )

    report = build_clean_review()
    TechnicalReviewQualityController._check_authentication(
        report,
        architecture,
        required,
        prohibited,
    )
    assert report.overall_status == "NEEDS_REVISION"
    assert any(
        finding.severity == "critical"
        and "explicit scope constraint" in finding.title.casefold()
        for finding in report.findings
    )


def test_affirmative_auth_requirement_is_still_detected() -> None:
    requirements = REQUIREMENTS.model_copy(
        update={
            "functional_requirements": [
                *REQUIREMENTS.functional_requirements,
                "Users must be able to log in with their credentials.",
            ],
            "constraints": [],
        }
    )
    required, prohibited = authentication_policy(requirements)
    assert required is True
    assert prohibited is False


def test_reviewer_ignores_neutral_authentication_sentinel() -> None:
    report = build_clean_review()
    report.findings.append(
        __import__(
            "app.agents.technical_reviewer.schemas",
            fromlist=["ReviewFinding"],
        ).ReviewFinding(
            category="assumption",
            severity="low",
            title="Authentication status clarification needed",
            evidence=(
                "Architecture states authentication is 'Not required based on current requirements', "
                "but requirement analysis does not mention authentication."
            ),
            recommendation=(
                "Label authentication as an architectural assumption."
            ),
        )
    )
    result = TechnicalReviewQualityController().validate(
        report=report,
        requirements=REQUIREMENTS,
        project_plan=build_plan(),
        architecture=build_clean_architecture(),
        registry=RequirementRegistry.from_analysis(REQUIREMENTS),
    )
    assert result.overall_status == "PASS"
    assert not any(
        "authentication status clarification" in finding.title.casefold()
        for finding in result.findings
    )


def test_unresolved_external_integration_has_action() -> None:
    architecture = build_clean_architecture()
    architecture.architectural_assumptions = [
        "Payment processing may require an external payment service.",
        "Delivery status may require data from a delivery provider.",
    ]
    result = TechnicalReviewQualityController().validate(
        report=build_clean_review(),
        requirements=REQUIREMENTS,
        project_plan=build_plan(),
        architecture=architecture,
        registry=RequirementRegistry.from_analysis(REQUIREMENTS),
    )
    assert result.overall_status == "PASS"
    assert any(
        "integration boundaries" in finding.title.casefold()
        for finding in result.findings
    )
    assert any("confirm" in action.casefold() for action in result.recommended_actions)
    assert "low-priority assumptions" in result.summary.casefold()


def main() -> None:
    test_architecture_quality_rejects_false_auth_provenance()
    test_reviewer_flags_false_auth_provenance()
    test_clean_architecture_remains_valid()
    test_architect_accepts_explicitly_negated_tracking_mention()
    test_architect_rejects_positive_unsupported_tracking_capability()
    test_reviewer_does_not_flag_negated_tracking_mention()
    test_reviewer_flags_positive_unsupported_tracking_capability()
    test_modal_tracking_assumption_is_reviewed_without_architect_retry()
    test_explicit_no_auth_constraint_overrides_keyword_mentions()
    test_affirmative_auth_requirement_is_still_detected()
    test_reviewer_ignores_neutral_authentication_sentinel()
    test_unresolved_external_integration_has_action()

    print("======================================================================")
    print("SEMANTIC INTEGRITY CONTRACT TEST: PASS")
    print("False authentication provenance: REJECTED")
    print("Technical reviewer escalation: PASS")
    print("Clean architecture baseline: PASS")
    print("Negated tracking mention: accepted")
    print("Positive unsupported tracking: rejected")
    print("Modal tracking assumption: surfaced for confirmation")
    print("Neutral authentication sentinel: accepted")
    print("Explicit no-auth constraint polarity: enforced")
    print("Unresolved integration: action generated")
    print("Reviewer polarity checks: PASS")
    print("======================================================================")


if __name__ == "__main__":
    main()
