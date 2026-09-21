from collections import Counter
import re

from app.agents.requirement_analyst.schemas import RequirementAnalysis

from .schemas import Milestone, ProjectPlan


class ProjectPlanQualityController:
    """
    Deterministic quality checks and normalization for ProjectPlan.

    Predictable structural and clearly unsupported wording issues are repaired
    locally so that another expensive LLM generation is not required.
    """

    def validate(
        self,
        plan: ProjectPlan,
        requirements: RequirementAnalysis,
    ) -> ProjectPlan:

        self._check_project_name(plan)

        self._normalize_empty_milestones(
            plan,
            requirements,
        )

        self._normalize_unsupported_language(
            plan,
            requirements,
        )

        self._check_milestones(plan)

        self._check_duplicate_milestones(plan)

        self._check_tasks(plan)

        self._check_requirement_references(
            plan,
            requirements,
        )

        self._set_development_sequence(plan)

        return plan

    @staticmethod
    def _check_project_name(
        plan: ProjectPlan,
    ) -> None:
        if not plan.project_name.strip():
            raise ValueError(
                "Project name cannot be empty."
            )

    @staticmethod
    def _normalize_empty_milestones(
        plan: ProjectPlan,
        requirements: RequirementAnalysis,
    ) -> None:
        """
        Create a minimal traceable fallback plan when the LLM returns an empty
        milestones list.
        """
        if plan.milestones:
            return

        functional_requirements = [
            requirement.strip()
            for requirement in requirements.functional_requirements
            if requirement.strip()
        ]

        if not functional_requirements:
            return

        generated_milestones: list[Milestone] = []

        for requirement in functional_requirements:
            milestone_name = (
                ProjectPlanQualityController
                ._milestone_name_from_requirement(
                    requirement
                )
            )

            generated_milestones.append(
                Milestone(
                    name=milestone_name,
                    description=requirement,
                    requirement_refs=[requirement],
                    tasks=[
                        "Define the work required to satisfy this requirement"
                    ],
                )
            )

        plan.milestones = generated_milestones

    @staticmethod
    def _milestone_name_from_requirement(
        requirement: str,
    ) -> str:
        cleaned = requirement.strip().rstrip(".")

        prefixes = (
            "Customers can ",
            "Customer can ",
            "Users can ",
            "User can ",
            "The system can ",
            "System can ",
        )

        for prefix in prefixes:
            if cleaned.casefold().startswith(
                prefix.casefold()
            ):
                cleaned = cleaned[len(prefix):]
                break

        cleaned = cleaned.strip()

        if not cleaned:
            return "Development Milestone"

        return cleaned[:1].upper() + cleaned[1:]

    @staticmethod
    def _normalize_unsupported_language(
        plan: ProjectPlan,
        requirements: RequirementAnalysis,
    ) -> None:
        """
        Remove clearly unsupported behavior qualifiers or provider-specific
        language when the RequirementAnalysis does not contain them.

        This intentionally handles only obvious, high-confidence cases.
        It does not attempt full semantic interpretation.
        """

        requirement_text = " ".join(
            requirement.strip().casefold()
            for requirement in requirements.functional_requirements
        )

        allows_realtime = (
            "real-time" in requirement_text
            or "real time" in requirement_text
            or "realtime" in requirement_text
        )

        for milestone in plan.milestones:
            milestone.description = (
                ProjectPlanQualityController
                ._normalize_text(
                    milestone.description,
                    allows_realtime=allows_realtime,
                    requirement_text=requirement_text,
                )
            )

            milestone.tasks = [
                ProjectPlanQualityController
                ._normalize_text(
                    task,
                    allows_realtime=allows_realtime,
                    requirement_text=requirement_text,
                )
                for task in milestone.tasks
            ]

        plan.dependencies = [
            ProjectPlanQualityController
            ._normalize_text(
                dependency,
                allows_realtime=allows_realtime,
                requirement_text=requirement_text,
            )
            for dependency in plan.dependencies
        ]

    @staticmethod
    def _normalize_text(
        text: str,
        *,
        allows_realtime: bool,
        requirement_text: str,
    ) -> str:
        normalized = text.strip()

        if not allows_realtime:
            normalized = re.sub(
                r"\breal[- ]time\b\s*",
                "",
                normalized,
                flags=re.IGNORECASE,
            )

            normalized = re.sub(
                r"\brealtime\b\s*",
                "",
                normalized,
                flags=re.IGNORECASE,
            )

        # High-confidence correction for an implementation-oriented
        # payment phrase that the planner should not introduce.
        if (
            "secure payment integration" not in requirement_text
            and normalized.casefold().strip()
            == "develop secure payment integration"
        ):
            normalized = "Develop payment processing workflow"

        # Remove accidental provider-specific planning terms unless the
        # requirement itself explicitly names the provider.
        providers = (
            "stripe",
            "paypal",
            "razorpay",
            "firebase",
            "twilio",
            "google maps",
        )

        for provider in providers:
            if provider in requirement_text:
                continue

            normalized = re.sub(
                rf"\b{re.escape(provider)}\b",
                "external service",
                normalized,
                flags=re.IGNORECASE,
            )

        # Clean up spacing caused by removing "real-time".
        normalized = re.sub(
            r"\s{2,}",
            " ",
            normalized,
        )

        normalized = re.sub(
            r"\s+([,.;:])",
            r"\1",
            normalized,
        )

        return normalized.strip()

    @staticmethod
    def _check_milestones(
        plan: ProjectPlan,
    ) -> None:
        if not plan.milestones:
            raise ValueError(
                "Project plan must contain at least one milestone."
            )

        for milestone in plan.milestones:
            if not milestone.name.strip():
                raise ValueError(
                    "Milestone name cannot be empty."
                )

            if not milestone.description.strip():
                raise ValueError(
                    f"Milestone '{milestone.name}' has no description."
                )

            if not milestone.requirement_refs:
                raise ValueError(
                    f"Milestone '{milestone.name}' has no requirement "
                    "references."
                )

            if not milestone.tasks:
                raise ValueError(
                    f"Milestone '{milestone.name}' has no tasks."
                )

    @staticmethod
    def _check_duplicate_milestones(
        plan: ProjectPlan,
    ) -> None:
        names = [
            milestone.name.strip().lower()
            for milestone in plan.milestones
        ]

        duplicates = [
            name
            for name, count in Counter(names).items()
            if count > 1
        ]

        if duplicates:
            raise ValueError(
                f"Duplicate milestones found: {duplicates}"
            )

    @staticmethod
    def _check_tasks(
        plan: ProjectPlan,
    ) -> None:
        for milestone in plan.milestones:
            normalized_tasks = [
                task.strip().lower()
                for task in milestone.tasks
            ]

            duplicates = [
                task
                for task, count in Counter(
                    normalized_tasks
                ).items()
                if count > 1
            ]

            if duplicates:
                raise ValueError(
                    f"Duplicate tasks found in "
                    f"'{milestone.name}': {duplicates}"
                )

    @staticmethod
    def _check_requirement_references(
        plan: ProjectPlan,
        requirements: RequirementAnalysis,
    ) -> None:
        valid_requirements = {
            requirement.strip()
            for requirement in requirements.functional_requirements
        }

        for milestone in plan.milestones:
            for reference in milestone.requirement_refs:
                if reference.strip() not in valid_requirements:
                    raise ValueError(
                        f"Invalid requirement reference in "
                        f"'{milestone.name}': {reference}"
                    )

    @staticmethod
    def _set_development_sequence(
        plan: ProjectPlan,
    ) -> None:
        plan.development_sequence = [
            milestone.name
            for milestone in plan.milestones
        ]