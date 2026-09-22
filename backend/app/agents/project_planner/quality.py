from collections import Counter

from app.core.traceability.requirements import RequirementRegistry

from app.agents.requirement_analyst.schemas import RequirementAnalysis

from .schemas import PlanTask, ProjectPlan


class ProjectPlanQualityController:
    """
    Deterministic validation and normalization for ProjectPlan.

    This controller validates structure and traceability.

    It does not silently rewrite task descriptions or invent missing
    project information.
    """

    def validate(
        self,
        plan: ProjectPlan,
        requirements: RequirementAnalysis,
        registry: RequirementRegistry,
    ) -> ProjectPlan:

        self._check_project_name(
            plan,
            requirements,
        )

        self._normalize_requirement_references(
            plan,
            registry,
        )

        self._check_milestones(
            plan,
        )

        self._check_duplicate_milestones(
            plan,
        )

        self._check_tasks(
            plan,
        )

        self._check_requirement_coverage(
            plan,
            registry,
        )

        self._check_task_traceability(
            plan,
            registry,
        )

        self._set_development_sequence(
            plan,
        )

        return plan

    @staticmethod
    def _check_project_name(
        plan: ProjectPlan,
        requirements: RequirementAnalysis,
    ) -> None:

        if plan.project_name.strip().casefold() != (
            requirements.project_name.strip().casefold()
        ):
            raise ValueError(
                "ProjectPlan project_name does not match "
                "RequirementAnalysis project_name."
            )

    @staticmethod
    def _normalize_requirement_references(
        plan: ProjectPlan,
        registry: RequirementRegistry,
    ) -> None:
        """
        Normalize both legacy text references and canonical IDs.

        No semantic rewriting is performed.

        A reference either resolves to one known requirement or validation
        fails.
        """

        for milestone in plan.milestones:

            milestone.requirement_refs = (
                registry.normalize_references(
                    milestone.requirement_refs
                )
            )

            normalized_tasks: list[PlanTask] = []

            for task in milestone.tasks:
                task.requirement_refs = (
                    registry.normalize_references(
                        task.requirement_refs
                    )
                )

                normalized_tasks.append(
                    task
                )

            milestone.tasks = normalized_tasks

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
                    f"Milestone '{milestone.name}' "
                    "has no description."
                )

            if not milestone.requirement_refs:
                raise ValueError(
                    f"Milestone '{milestone.name}' "
                    "has no requirement references."
                )

            if not milestone.tasks:
                raise ValueError(
                    f"Milestone '{milestone.name}' "
                    "has no tasks."
                )

    @staticmethod
    def _check_duplicate_milestones(
        plan: ProjectPlan,
    ) -> None:

        names = [
            milestone.name.strip().casefold()
            for milestone in plan.milestones
        ]

        duplicates = [
            name
            for name, count in Counter(
                names
            ).items()
            if count > 1
        ]

        if duplicates:
            raise ValueError(
                f"Duplicate milestones found: "
                f"{duplicates}"
            )

    @staticmethod
    def _check_tasks(
        plan: ProjectPlan,
    ) -> None:

        for milestone in plan.milestones:

            task_descriptions = [
                task.description.strip().casefold()
                for task in milestone.tasks
            ]

            if any(
                not task.description.strip()
                for task in milestone.tasks
            ):
                raise ValueError(
                    f"Milestone '{milestone.name}' "
                    "contains an empty task."
                )

            duplicates = [
                description
                for description, count in Counter(
                    task_descriptions
                ).items()
                if count > 1
            ]

            if duplicates:
                raise ValueError(
                    f"Duplicate tasks found in "
                    f"'{milestone.name}': "
                    f"{duplicates}"
                )

    @staticmethod
    def _check_requirement_coverage(
        plan: ProjectPlan,
        registry: RequirementRegistry,
    ) -> None:

        covered_ids = {
            reference
            for milestone in plan.milestones
            for reference in milestone.requirement_refs
        }

        required_ids = set(
            registry.ids
        )

        missing_ids = (
            required_ids - covered_ids
        )

        if missing_ids:
            missing_details = [
                (
                    f"{requirement_id}: "
                    f"{registry.text_for_id(requirement_id)}"
                )
                for requirement_id in sorted(
                    missing_ids
                )
            ]

            raise ValueError(
                "Project plan does not cover all functional "
                "requirements. Missing: "
                f"{missing_details}"
            )

    @staticmethod
    def _check_task_traceability(
        plan: ProjectPlan,
        registry: RequirementRegistry,
    ) -> None:

        valid_ids = set(
            registry.ids
        )

        for milestone in plan.milestones:

            milestone_ids = set(
                milestone.requirement_refs
            )

            for task in milestone.tasks:

                task_ids = set(
                    task.requirement_refs
                )

                unknown_ids = (
                    task_ids - valid_ids
                )

                if unknown_ids:
                    raise ValueError(
                        f"Task '{task.description}' in milestone "
                        f"'{milestone.name}' references unknown "
                        f"requirements: "
                        f"{sorted(unknown_ids)}"
                    )

                outside_milestone = (
                    task_ids - milestone_ids
                )

                if outside_milestone:
                    raise ValueError(
                        f"Task '{task.description}' in milestone "
                        f"'{milestone.name}' references requirements "
                        f"outside the milestone scope: "
                        f"{sorted(outside_milestone)}"
                    )

                if not task_ids:
                    raise ValueError(
                        f"Task '{task.description}' in milestone "
                        f"'{milestone.name}' has no requirement "
                        "references."
                    )

    @staticmethod
    def _set_development_sequence(
        plan: ProjectPlan,
    ) -> None:

        plan.development_sequence = [
            milestone.name
            for milestone in plan.milestones
        ]