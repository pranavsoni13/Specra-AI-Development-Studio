from collections import Counter

from .schemas import RequirementAnalysis


class RequirementQualityController:
    """
    Deterministic quality checks for RequirementAnalysis.

    This layer does not generate new information.
    It only cleans, validates, and flags obvious quality problems.
    """

    def validate(
        self,
        analysis: RequirementAnalysis,
    ) -> RequirementAnalysis:
        self._check_project_name(analysis)
        self._check_objective(analysis)
        self._check_duplicates(analysis)
        self._check_empty_items(analysis)

        return analysis

    @staticmethod
    def _check_project_name(
        analysis: RequirementAnalysis,
    ) -> None:
        if not analysis.project_name.strip():
            raise ValueError("Project name cannot be empty.")

    @staticmethod
    def _check_objective(
        analysis: RequirementAnalysis,
    ) -> None:
        if not analysis.objective.strip():
            raise ValueError("Project objective cannot be empty.")

    @staticmethod
    def _check_duplicates(
        analysis: RequirementAnalysis,
    ) -> None:
        list_fields = [
            "user_roles",
            "functional_requirements",
            "non_functional_requirements",
            "constraints",
            "assumptions",
            "risks",
            "clarifications_needed",
        ]

        for field_name in list_fields:
            values = getattr(analysis, field_name)

            normalized = [
                value.strip().lower()
                for value in values
                if isinstance(value, str)
            ]

            duplicates = [
                item
                for item, count in Counter(normalized).items()
                if count > 1
            ]

            if duplicates:
                raise ValueError(
                    f"Duplicate entries found in '{field_name}': "
                    f"{duplicates}"
                )

    @staticmethod
    def _check_empty_items(
        analysis: RequirementAnalysis,
    ) -> None:
        list_fields = [
            "user_roles",
            "functional_requirements",
            "non_functional_requirements",
            "constraints",
            "assumptions",
            "risks",
            "clarifications_needed",
        ]

        for field_name in list_fields:
            values = getattr(analysis, field_name)

            if any(
                not isinstance(value, str) or not value.strip()
                for value in values
            ):
                raise ValueError(
                    f"Empty or invalid item found in '{field_name}'."
                )