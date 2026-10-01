from collections import Counter

from app.core.traceability.requirements import RequirementRegistry

from app.agents.project_planner.schemas import ProjectPlan
from app.agents.requirement_analyst.schemas import RequirementAnalysis
from app.agents.software_architect.schemas import SystemArchitecture

from .schemas import ReviewFinding, ReviewReport


class TechnicalReviewQualityController:
    """
    Deterministic validation for ReviewReport.

    The controller independently validates:
    - project identity
    - requirement coverage
    - traceability
    - findings structure
    - architecture consistency
    - obvious unsupported capabilities
    - review status consistency
    """

    def validate(
        self,
        report: ReviewReport,
        requirements: RequirementAnalysis,
        project_plan: ProjectPlan,
        architecture: SystemArchitecture,
        registry: RequirementRegistry | None = None,
    ) -> ReviewReport:

        if not isinstance(
            report,
            ReviewReport,
        ):
            raise TypeError(
                "report must be an instance of ReviewReport."
            )

        if registry is None:
            registry = RequirementRegistry.from_analysis(
                requirements
            )

        self._check_project_name(
            report=report,
            requirements=requirements,
        )

        self._check_coverage(
            report=report,
            requirements=requirements,
            project_plan=project_plan,
            architecture=architecture,
            registry=registry,
        )

        self._check_findings(
            report=report,
        )

        self._apply_deterministic_architecture_checks(
            report=report,
            requirements=requirements,
            architecture=architecture,
            registry=registry,
        )

        self._check_status(
            report=report,
        )

        self._check_problem_consistency(
            report=report,
        )

        return report

    @staticmethod
    def _check_project_name(
        report: ReviewReport,
        requirements: RequirementAnalysis,
    ) -> None:

        if (
            report.project_name.strip().casefold()
            != requirements.project_name.strip().casefold()
        ):
            raise ValueError(
                "Review report project_name does not match "
                "RequirementAnalysis project_name."
            )

    @staticmethod
    def _check_coverage(
        report: ReviewReport,
        requirements: RequirementAnalysis,
        project_plan: ProjectPlan,
        architecture: SystemArchitecture,
        registry: RequirementRegistry,
    ) -> None:

        required_ids = set(
            registry.ids
        )

        plan_refs: set[str] = set()

        for milestone in project_plan.milestones:
            plan_refs.update(
                registry.normalize_references(
                    milestone.requirement_refs
                )
            )

            for task in milestone.tasks:
                task_refs = registry.normalize_references(
                    task.requirement_refs
                )

                plan_refs.update(task_refs)

                if not set(task_refs).issubset(
                    set(
                        registry.normalize_references(
                            milestone.requirement_refs
                        )
                    )
                ):
                    raise ValueError(
                        f"ProjectPlan task '{task.description}' contains "
                        "requirement references outside its parent milestone."
                    )

        component_refs: set[str] = set()

        for component in architecture.components:
            component_refs.update(
                registry.normalize_references(
                    component.related_requirements
                )
            )

        api_refs: set[str] = set()

        for endpoint in architecture.api_endpoints:
            api_refs.update(
                registry.normalize_references(
                    endpoint.related_requirements
                )
            )

        report_ids: list[str] = []

        for coverage in report.requirement_coverage:

            requirement_id = registry.normalize_reference(
                coverage.requirement_id
            )

            report_ids.append(
                requirement_id
            )

            expected_text = registry.text_for_id(
                requirement_id
            )

            if coverage.requirement.strip() != expected_text.strip():
                raise ValueError(
                    f"Requirement text mismatch for {requirement_id}."
                )

            expected_plan = (
                requirement_id in plan_refs
            )

            expected_architecture = (
                requirement_id in component_refs
            )

            expected_api = (
                requirement_id in api_refs
            )

            if coverage.in_project_plan != expected_plan:
                raise ValueError(
                    "Incorrect project-plan coverage for "
                    f"{requirement_id}."
                )

            if coverage.in_architecture != expected_architecture:
                raise ValueError(
                    "Incorrect architecture coverage for "
                    f"{requirement_id}."
                )

            if coverage.in_api != expected_api:
                raise ValueError(
                    "Incorrect API coverage for "
                    f"{requirement_id}."
                )

        duplicate_ids = [
            requirement_id
            for requirement_id, count in Counter(
                report_ids
            ).items()
            if count > 1
        ]

        if duplicate_ids:
            raise ValueError(
                "Review report contains duplicate requirement coverage "
                f"entries: {duplicate_ids}"
            )

        report_id_set = set(
            report_ids
        )

        missing_ids = required_ids - report_id_set

        if missing_ids:
            raise ValueError(
                "Review report is missing requirement coverage entries: "
                f"{sorted(missing_ids)}"
            )

        extra_ids = report_id_set - required_ids

        if extra_ids:
            raise ValueError(
                "Review report contains invalid requirement IDs: "
                f"{sorted(extra_ids)}"
            )

        if report_id_set != required_ids:
            raise ValueError(
                "Review report requirement coverage does not exactly "
                "match the authoritative functional requirements."
            )

    @staticmethod
    def _check_findings(
        report: ReviewReport,
    ) -> None:

        titles = [
            finding.title.strip().casefold()
            for finding in report.findings
        ]

        duplicates = [
            title
            for title, count in Counter(
                titles
            ).items()
            if count > 1
        ]

        if duplicates:
            raise ValueError(
                f"Duplicate review findings found: {duplicates}"
            )

        for finding in report.findings:

            if not finding.title.strip():
                raise ValueError(
                    "Review finding title cannot be empty."
                )

            if not finding.evidence.strip():
                raise ValueError(
                    f"Review finding '{finding.title}' "
                    "must contain evidence."
                )

            if not finding.recommendation.strip():
                raise ValueError(
                    f"Review finding '{finding.title}' "
                    "must contain a recommendation."
                )

    @staticmethod
    def _apply_deterministic_architecture_checks(
        report: ReviewReport,
        requirements: RequirementAnalysis,
        architecture: SystemArchitecture,
        registry: RequirementRegistry,
    ) -> None:
        """
        Add only high-confidence deterministic findings.

        These checks supplement the LLM review. They do not rewrite
        architectural content.
        """

        requirement_text = " ".join(
            [
                requirements.objective,
                *requirements.functional_requirements,
                *requirements.non_functional_requirements,
                *requirements.constraints,
            ]
        ).casefold()

        architecture_text = " ".join(
            [
                architecture.frontend,
                architecture.backend,
                architecture.database,
                architecture.authentication,
                *architecture.data_flow,
                *architecture.external_integrations,
                *architecture.architectural_assumptions,
                *[
                    component.name
                    for component in architecture.components
                ],
                *[
                    component.responsibility
                    for component in architecture.components
                ],
                *[
                    endpoint.name
                    for endpoint in architecture.api_endpoints
                ],
                *[
                    endpoint.purpose
                    for endpoint in architecture.api_endpoints
                ],
                *[
                    decision.decision
                    for decision in architecture.architecture_decisions
                ],
                *[
                    decision.rationale
                    for decision in architecture.architecture_decisions
                ],
            ]
        ).casefold()

        authentication_required = any(
            keyword in requirement_text
            for keyword in (
                "authentication",
                "authenticate",
                "login",
                "log in",
                "sign in",
                "signin",
                "signup",
                "sign up",
                "authorization",
                "authorisation",
                "password",
                "user credentials",
            )
        )

        selected_authentication = (
            architecture.authentication.strip()
        )

        authentication_is_none = selected_authentication.casefold() in {
            "none",
            "not required",
            "not required based on current requirements",
            "no authentication",
            "no authentication required",
        }

        if (
            not authentication_required
            and selected_authentication
            and not authentication_is_none
        ):
            self_title = (
                "Authentication introduced without explicit "
                "requirement support"
            )

            self._add_finding(
                report=report,
                finding=ReviewFinding(
                    category="assumption",
                    severity="medium",
                    title=self_title,
                    evidence=(
                        "SystemArchitecture selects "
                        f"'{selected_authentication}', but the "
                        "authoritative RequirementAnalysis does not "
                        "contain an explicit authentication-related "
                        "requirement."
                    ),
                    recommendation=(
                        "Either obtain explicit confirmation that "
                        "authentication is required, or label the "
                        "authentication approach as an architectural "
                        "assumption rather than a confirmed requirement."
                    ),
                ),
                consistency_issue=(
                    "Authentication was introduced without explicit "
                    "authentication-related requirements."
                ),
                unsupported_addition=(
                    "Authentication was introduced without explicit "
                    "authentication-related requirements."
                ),
                action=(
                    "Clarify whether authentication is required before "
                    "treating the selected authentication architecture "
                    "as confirmed."
                ),
            )

        realtime_required = any(
            term in requirement_text
            for term in (
                "real-time",
                "realtime",
                "live tracking",
                "live updates",
                "instant updates",
            )
        )

        if not realtime_required:
            realtime_terms = (
                "real-time",
                "realtime",
                "websocket",
                "web sockets",
                "gps tracking",
                "live gps",
                "push notification",
                "push notifications",
            )

            found = sorted(
                {
                    term
                    for term in realtime_terms
                    if term in architecture_text
                }
            )

            if found:
                title = (
                    "Unsupported real-time or advanced tracking behavior"
                )

                self._add_finding(
                    report=report,
                    finding=ReviewFinding(
                        category="architecture",
                        severity="high",
                        title=title,
                        evidence=(
                            "SystemArchitecture contains unsupported "
                            "real-time or advanced tracking terms: "
                            + ", ".join(found)
                        ),
                        recommendation=(
                            "Remove the unsupported behavior unless "
                            "the user explicitly requires it."
                        ),
                    ),
                    consistency_issue=(
                        "Architecture introduces unsupported real-time "
                        "or advanced tracking behavior."
                    ),
                    unsupported_addition=(
                        "Unsupported real-time or advanced tracking "
                        "behavior was introduced."
                    ),
                    action=(
                        "Remove unsupported real-time or advanced "
                        "tracking behavior or obtain explicit "
                        "requirement support."
                    ),
                )

        discovery_required = any(
            term in requirement_text
            for term in (
                "discover restaurants",
                "restaurant discovery",
                "browse restaurants",
            )
        )

        if discovery_required:
            discovery_terms = (
                "user location",
                "location-based",
                "location based",
                "gps",
                "user preferences",
                "preferences",
                "personalization",
                "personalisation",
                "recommendation",
                "recommended restaurants",
            )

            found = sorted(
                {
                    term
                    for term in discovery_terms
                    if term in architecture_text
                }
            )

            if found:
                title = (
                    "Unsupported restaurant-discovery behavior"
                )

                self._add_finding(
                    report=report,
                    finding=ReviewFinding(
                        category="architecture",
                        severity="medium",
                        title=title,
                        evidence=(
                            "SystemArchitecture introduces restaurant "
                            "discovery behavior not established by "
                            "RequirementAnalysis: "
                            + ", ".join(found)
                        ),
                        recommendation=(
                            "Keep restaurant discovery at the level "
                            "specified by the requirements unless the "
                            "additional behavior is explicitly confirmed."
                        ),
                    ),
                    consistency_issue=(
                        "Architecture introduces unsupported "
                        "restaurant-discovery behavior."
                    ),
                    unsupported_addition=(
                        "Unsupported restaurant-discovery behavior "
                        "was introduced."
                    ),
                    action=(
                        "Remove unsupported restaurant-discovery "
                        "behavior or clarify the requirement."
                    ),
                )

        project_plan_refs = set()

        for component in architecture.components:
            project_plan_refs.update(
                registry.normalize_references(
                    component.related_requirements
                )
            )

        for requirement_id in registry.ids:
            if requirement_id not in project_plan_refs:
                continue

        api_requirement_ids = set()

        for endpoint in architecture.api_endpoints:
            api_requirement_ids.update(
                registry.normalize_references(
                    endpoint.related_requirements
                )
            )

        missing_api_ids = [
            requirement_id
            for requirement_id in registry.ids
            if requirement_id not in api_requirement_ids
        ]

        if missing_api_ids:
            title = (
                "Functional requirements missing API coverage"
            )

            self._add_finding(
                report=report,
                finding=ReviewFinding(
                    category="traceability",
                    severity="high",
                    title=title,
                    evidence=(
                        "The following functional requirements are not "
                        "represented by an API capability: "
                        + ", ".join(missing_api_ids)
                    ),
                    recommendation=(
                        "Add requirement-derived API capabilities or "
                        "clarify why backend interaction is not needed."
                    ),
                ),
                consistency_issue=(
                    "One or more functional requirements lack API coverage."
                ),
                action=(
                    "Add API capabilities for the uncovered functional "
                    "requirements."
                ),
            )

    @staticmethod
    def _add_finding(
        report: ReviewReport,
        finding: ReviewFinding,
        consistency_issue: str | None = None,
        unsupported_addition: str | None = None,
        action: str | None = None,
    ) -> None:

        existing_titles = {
            item.title.strip().casefold()
            for item in report.findings
        }

        if finding.title.strip().casefold() not in existing_titles:
            report.findings.append(
                finding
            )

        if (
            consistency_issue
            and consistency_issue not in report.architecture_consistency_issues
        ):
            report.architecture_consistency_issues.append(
                consistency_issue
            )

        if (
            unsupported_addition
            and unsupported_addition
            not in report.unsupported_additions
        ):
            report.unsupported_additions.append(
                unsupported_addition
            )

        if (
            action
            and action not in report.recommended_actions
        ):
            report.recommended_actions.append(
                action
            )

        if finding.severity in {
            "medium",
            "high",
            "critical",
        }:
            report.overall_status = "NEEDS_REVISION"

    @staticmethod
    def _check_status(
        report: ReviewReport,
    ) -> None:

        serious_findings = any(
            finding.severity in {
                "high",
                "critical",
            }
            for finding in report.findings
        )

        material_findings = any(
            finding.severity in {
                "medium",
                "high",
                "critical",
            }
            for finding in report.findings
        )

        has_material_issues = (
            bool(
                report.unsupported_additions
                or report.architecture_consistency_issues
            )
            or material_findings
        )

        if (
            serious_findings
            and report.overall_status == "PASS"
        ):
            raise ValueError(
                "Review cannot be PASS when high or critical findings exist."
            )

        if (
            has_material_issues
            and report.overall_status == "PASS"
        ):
            raise ValueError(
                "Review cannot be PASS when material findings or "
                "architecture issues are present."
            )

        if (
            report.overall_status == "NEEDS_REVISION"
            and not has_material_issues
        ):
            raise ValueError(
                "Review is marked NEEDS_REVISION but no material "
                "review problem was identified."
            )

    @staticmethod
    def _check_problem_consistency(
        report: ReviewReport,
    ) -> None:

        has_problem_lists = bool(
            report.unsupported_additions
            or report.architecture_consistency_issues
        )

        if (
            has_problem_lists
            and not report.findings
        ):
            raise ValueError(
                "Review reported unsupported additions or architecture "
                "issues but findings is empty."
            )

        material_finding_titles = {
            finding.title.strip().casefold()
            for finding in report.findings
            if finding.severity in {
                "medium",
                "high",
                "critical",
            }
        }

        if (
            report.overall_status == "NEEDS_REVISION"
            and not material_finding_titles
            and not has_problem_lists
        ):
            raise ValueError(
                "Review is marked NEEDS_REVISION without a material "
                "finding or problem category."
            )