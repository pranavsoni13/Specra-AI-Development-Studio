import re
from collections import Counter

from .schemas import RequirementAnalysis


class RequirementQualityController:
    """
    Deterministic quality checks and normalization for RequirementAnalysis.

    This layer does not invent project information. It only:
    - validates required fields
    - removes duplicate entries
    - normalizes whitespace
    - recovers explicitly stated/implied user roles
    """

    # Conservative mappings only.
    # We only infer a role when the wording clearly identifies an actor.
    ROLE_PATTERNS = {
        "customer": r"\bcustomers?\b",
        "user": r"\busers?\b",
        "administrator": r"\badministrators?\b|\badmins?\b",
        "restaurant owner": r"\brestaurant owners?\b",
        "delivery partner": r"\bdelivery partners?\b",
        "driver": r"\bdrivers?\b",
        "doctor": r"\bdoctors?\b",
        "student": r"\bstudents?\b",
        "teacher": r"\bteachers?\b",
        "employee": r"\bemployees?\b",
        "manager": r"\bmanagers?\b",
    }

    ROLE_DISPLAY_NAMES = {
        "customer": "Customer",
        "user": "User",
        "administrator": "Administrator",
        "restaurant owner": "Restaurant Owner",
        "delivery partner": "Delivery Partner",
        "driver": "Driver",
        "doctor": "Doctor",
        "student": "Student",
        "teacher": "Teacher",
        "employee": "Employee",
        "manager": "Manager",
    }

    def validate(
        self,
        analysis: RequirementAnalysis,
    ) -> RequirementAnalysis:
        self._check_project_name(analysis)
        self._check_objective(analysis)

        self._normalize_lists(analysis)
        self._remove_duplicates(analysis)
        self._recover_explicit_roles(analysis)
        self._check_empty_items(analysis)

        return analysis

    @staticmethod
    def _check_project_name(
        analysis: RequirementAnalysis,
    ) -> None:
        if not analysis.project_name.strip():
            raise ValueError(
                "Project name cannot be empty."
            )

    @staticmethod
    def _check_objective(
        analysis: RequirementAnalysis,
    ) -> None:
        if not analysis.objective.strip():
            raise ValueError(
                "Project objective cannot be empty."
            )

    @staticmethod
    def _normalize_text(value: str) -> str:
        """
        Normalize ordinary whitespace without attempting
        grammar correction or semantic rewriting.
        """
        return " ".join(value.split()).strip()

    def _normalize_lists(
        self,
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

            normalized_values = [
                self._normalize_text(value)
                for value in values
                if isinstance(value, str)
            ]

            setattr(
                analysis,
                field_name,
                normalized_values,
            )

        analysis.project_name = self._normalize_text(
            analysis.project_name
        )

        analysis.objective = self._normalize_text(
            analysis.objective
        )

    @staticmethod
    def _remove_duplicates(
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

            seen = set()
            unique_values = []

            for value in values:
                key = value.casefold()

                if key not in seen:
                    seen.add(key)
                    unique_values.append(value)

            setattr(
                analysis,
                field_name,
                unique_values,
            )

    def _recover_explicit_roles(
        self,
        analysis: RequirementAnalysis,
    ) -> None:
        """
        Recover roles that are explicitly represented in functional
        requirement wording.

        Example:
        "Customers can place orders"
        -> "Customer"

        This deliberately uses a small allow-list rather than
        attempting general NLP-based role extraction.
        """

        existing_roles = {
            role.casefold().strip()
            for role in analysis.user_roles
        }

        requirement_text = " ".join(
            analysis.functional_requirements
        ).casefold()

        for role_key, pattern in self.ROLE_PATTERNS.items():
            if re.search(pattern, requirement_text):
                display_name = self.ROLE_DISPLAY_NAMES[role_key]

                if display_name.casefold() not in existing_roles:
                    analysis.user_roles.append(display_name)
                    existing_roles.add(
                        display_name.casefold()
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
                not isinstance(value, str)
                or not value.strip()
                for value in values
            ):
                raise ValueError(
                    f"Empty or invalid item found in "
                    f"'{field_name}'."
                )