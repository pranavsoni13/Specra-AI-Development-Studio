from collections import Counter

from app.agents.project_planner.schemas import ProjectPlan
from app.agents.requirement_analyst.schemas import RequirementAnalysis
from app.agents.software_architect.schemas import SystemArchitecture

from .schemas import ReviewReport, ReviewFinding


class TechnicalReviewQualityController:
    """
    Deterministic validation and normalization for ReviewReport.

    The controller validates the review itself and also enforces
    important project-level consistency rules that must not depend
    entirely on LLM judgment.
    """

    def validate(
        self,
        report: ReviewReport,
        requirements: RequirementAnalysis,
        project_plan: ProjectPlan,
        architecture: SystemArchitecture,
    ) -> ReviewReport:

        self._check_project_name(
            report,
            requirements,
        )

        self._check_coverage(
            report,
            requirements,
            project_plan,
            architecture,
        )

        self._check_findings(
            report,
        )

        self._apply_deterministic_architecture_checks(
            report,
            requirements,
            architecture,
        )

        self._check_status(
            report,
        )

        self._check_problem_consistency(
            report,
        )

        return report

    @staticmethod
    def _check_project_name(
        report: ReviewReport,
        requirements: RequirementAnalysis,
    ) -> None:
        if report.project_name.strip().casefold() != (
            requirements.project_name.strip().casefold()
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
    ) -> None:
        required = {
            item.strip()
            for item in requirements.functional_requirements
        }

        plan_refs = {
            reference.strip()
            for milestone in project_plan.milestones
            for reference in milestone.requirement_refs
        }

        architecture_refs = {
            reference.strip()
            for component in architecture.components
            for reference in component.related_requirements
        }

        report_requirements = {
            coverage.requirement.strip()
            for coverage in report.requirement_coverage
        }

        missing_report_entries = required - report_requirements

        if missing_report_entries:
            raise ValueError(
                "Review report is missing requirement coverage entries: "
                f"{sorted(missing_report_entries)}"
            )

        if report_requirements != required:
            extra_entries = report_requirements - required

            if extra_entries:
                raise ValueError(
                    "Review report contains invalid requirement entries: "
                    f"{sorted(extra_entries)}"
                )

        for coverage in report.requirement_coverage:
            requirement = coverage.requirement.strip()

            if requirement not in required:
                raise ValueError(
                    f"Invalid requirement in review coverage: {requirement}"
                )

            expected_plan = requirement in plan_refs
            expected_architecture = requirement in architecture_refs

            if coverage.in_project_plan != expected_plan:
                raise ValueError(
                    f"Incorrect project-plan coverage for requirement: "
                    f"{requirement}"
                )

            if coverage.in_architecture != expected_architecture:
                raise ValueError(
                    f"Incorrect architecture coverage for requirement: "
                    f"{requirement}"
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
            for title, count in Counter(titles).items()
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
    ) -> None:
        """
        Enforce important architecture-review rules deterministically.

        These checks exist because an LLM reviewer may occasionally
        overlook a contradiction that can be established directly
        from the structured artifacts.
        """

        requirement_text = " ".join(
            [
                requirements.objective,
                *requirements.functional_requirements,
                *requirements.non_functional_requirements,
                *requirements.constraints,
            ]
        ).casefold()

        authentication_keywords = (
            "authentication",
            "authenticate",
            "login",
            "log in",
            "sign in",
            "signin",
            "account",
            "authorization",
            "role-based access",
            "access control",
            "user credentials",
            "password",
        )

        authentication_required_by_input = any(
            keyword in requirement_text
            for keyword in authentication_keywords
        )

        selected_authentication = (
            architecture.authentication.strip()
        )

        authentication_was_selected = (
            selected_authentication
            and selected_authentication.casefold()
            != "not required based on current requirements"
        )

        if (
            authentication_was_selected
            and not authentication_required_by_input
        ):
            existing_titles = {
                finding.title.strip().casefold()
                for finding in report.findings
            }

            title = (
                "Authentication introduced without explicit "
                "requirement support"
            )

            if title.casefold() not in existing_titles:
                report.findings.append(
                    ReviewFinding(
                        category="assumption",
                        severity="medium",
                        title=title,
                        evidence=(
                            "SystemArchitecture selects "
                            f"'{selected_authentication}', but "
                            "RequirementAnalysis does not explicitly "
                            "contain authentication, login, account, "
                            "authorization, or access-control requirements."
                        ),
                        recommendation=(
                            "Either obtain explicit confirmation that "
                            "authentication is required, or clearly label "
                            "the authentication approach as an architectural "
                            "assumption rather than an established requirement."
                        ),
                    )
                )

            if not any(
                issue.casefold()
                == title.casefold()
                for issue in report.architecture_consistency_issues
            ):
                report.architecture_consistency_issues.append(
                    "Authentication was introduced without explicit "
                    "authentication-related requirements."
                )

            if not any(
                addition.casefold()
                == title.casefold()
                for addition in report.unsupported_additions
            ):
                report.unsupported_additions.append(
                    "Authentication was introduced without explicit "
                    "authentication-related requirements."
                )

            report.overall_status = "NEEDS_REVISION"

            action = (
                "Clarify whether authentication and authorization are "
                "required before treating the selected authentication "
                "architecture as confirmed."
            )

            if action not in report.recommended_actions:
                report.recommended_actions.append(
                    action
                )

    @staticmethod
    def _check_status(
        report: ReviewReport,
    ) -> None:
        has_serious_findings = any(
            finding.severity in {"high", "critical"}
            for finding in report.findings
        )

        if has_serious_findings and report.overall_status == "PASS":
            raise ValueError(
                "Review cannot be PASS when high or critical findings exist."
            )

        if (
            report.findings
            or report.unsupported_additions
            or report.architecture_consistency_issues
        ):
            if report.overall_status == "PASS":
                raise ValueError(
                    "Review cannot be PASS when material findings or "
                    "architecture issues are present."
                )

    @staticmethod
    def _check_problem_consistency(
        report: ReviewReport,
    ) -> None:
        has_reported_problems = bool(
            report.unsupported_additions
            or report.architecture_consistency_issues
            or report.findings
            or report.recommended_actions
        )

        if (
            report.overall_status == "NEEDS_REVISION"
            and not has_reported_problems
        ):
            raise ValueError(
                "Review is marked NEEDS_REVISION but contains no "
                "identified problems."
            )

        has_problem_categories = bool(
            report.unsupported_additions
            or report.architecture_consistency_issues
        )

        if has_problem_categories and not report.findings:
            raise ValueError(
                "Unsupported additions or architecture consistency issues "
                "were reported, but findings is empty."
            )