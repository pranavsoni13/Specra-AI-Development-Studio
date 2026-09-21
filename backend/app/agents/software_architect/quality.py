from collections import Counter

from app.agents.project_planner.schemas import ProjectPlan
from app.agents.requirement_analyst.schemas import RequirementAnalysis

from .schemas import SystemArchitecture


class ArchitectureQualityController:
    """
    Deterministic validation and normalization for SystemArchitecture.
    """

    def validate(
        self,
        architecture: SystemArchitecture,
        requirements: RequirementAnalysis,
        project_plan: ProjectPlan,
    ) -> SystemArchitecture:

        self._check_project_name(
            architecture,
            requirements,
        )

        self._check_required_fields(
            architecture,
        )

        self._check_component_references(
            architecture,
            requirements,
        )

        self._check_api_references(
            architecture,
            requirements,
        )

        self._check_duplicates(
            architecture,
        )

        self._normalize_unsupported_behavior(
            architecture,
            requirements,
        )

        self._normalize_external_integrations(
            architecture,
        )

        self._check_external_integrations(
            architecture,
        )

        self._check_architecture_consistency(
            architecture,
        )

        return architecture

    @staticmethod
    def _check_project_name(
        architecture: SystemArchitecture,
        requirements: RequirementAnalysis,
    ) -> None:
        if architecture.project_name.strip().casefold() != (
            requirements.project_name.strip().casefold()
        ):
            raise ValueError(
                "Architecture project_name does not match "
                "RequirementAnalysis project_name."
            )

    @staticmethod
    def _check_required_fields(
        architecture: SystemArchitecture,
    ) -> None:
        required_fields = {
            "architecture_style": architecture.architecture_style,
            "frontend": architecture.frontend,
            "backend": architecture.backend,
            "database": architecture.database,
            "authentication": architecture.authentication,
        }

        for field_name, value in required_fields.items():
            if not value or not value.strip():
                raise ValueError(
                    f"Architecture field '{field_name}' cannot be empty."
                )

        if not architecture.components:
            raise ValueError(
                "Architecture must contain at least one component."
            )

        if not architecture.data_flow:
            raise ValueError(
                "Architecture must contain at least one data-flow statement."
            )

        if not architecture.architecture_decisions:
            raise ValueError(
                "Architecture must contain at least one architecture decision."
            )

    @staticmethod
    def _check_component_references(
        architecture: SystemArchitecture,
        requirements: RequirementAnalysis,
    ) -> None:
        valid_requirements = {
            requirement.strip()
            for requirement in requirements.functional_requirements
        }

        for component in architecture.components:
            if not component.name.strip():
                raise ValueError(
                    "Architecture component name cannot be empty."
                )

            if not component.responsibility.strip():
                raise ValueError(
                    f"Architecture component '{component.name}' "
                    "must have a responsibility."
                )

            if not component.related_requirements:
                raise ValueError(
                    f"Architecture component '{component.name}' "
                    "must reference at least one requirement."
                )

            for reference in component.related_requirements:
                if reference.strip() not in valid_requirements:
                    raise ValueError(
                        f"Invalid requirement reference in component "
                        f"'{component.name}': {reference}"
                    )

    @staticmethod
    def _check_api_references(
        architecture: SystemArchitecture,
        requirements: RequirementAnalysis,
    ) -> None:
        valid_requirements = {
            requirement.strip()
            for requirement in requirements.functional_requirements
        }

        for endpoint in architecture.api_endpoints:
            if not endpoint.name.strip():
                raise ValueError(
                    "API capability name cannot be empty."
                )

            if not endpoint.purpose.strip():
                raise ValueError(
                    f"API capability '{endpoint.name}' "
                    "must have a purpose."
                )

            if not endpoint.related_requirements:
                raise ValueError(
                    f"API capability '{endpoint.name}' "
                    "must reference at least one requirement."
                )

            for reference in endpoint.related_requirements:
                if reference.strip() not in valid_requirements:
                    raise ValueError(
                        f"Invalid requirement reference in API capability "
                        f"'{endpoint.name}': {reference}"
                    )

    @staticmethod
    def _check_duplicates(
        architecture: SystemArchitecture,
    ) -> None:
        component_names = [
            component.name.strip().casefold()
            for component in architecture.components
        ]

        duplicate_components = [
            name
            for name, count in Counter(component_names).items()
            if count > 1
        ]

        if duplicate_components:
            raise ValueError(
                f"Duplicate architecture components found: "
                f"{duplicate_components}"
            )

        endpoint_names = [
            endpoint.name.strip().casefold()
            for endpoint in architecture.api_endpoints
        ]

        duplicate_endpoints = [
            name
            for name, count in Counter(endpoint_names).items()
            if count > 1
        ]

        if duplicate_endpoints:
            raise ValueError(
                f"Duplicate API capabilities found: "
                f"{duplicate_endpoints}"
            )

    @staticmethod
    def _build_external_context(
        architecture: SystemArchitecture,
    ) -> str:
        """
        Build text used specifically for external-integration detection.

        Authentication is intentionally excluded because a valid value such as
        "Not required based on current requirements" must not suppress detection
        of a real external integration elsewhere in the architecture.
        """
        return " ".join(
            [
                architecture.frontend,
                architecture.backend,
                architecture.database,
                *[
                    component.responsibility
                    for component in architecture.components
                ],
                *architecture.data_flow,
                *architecture.architectural_assumptions,
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

    @staticmethod
    def _normalize_unsupported_behavior(
        architecture: SystemArchitecture,
        requirements: RequirementAnalysis,
    ) -> None:
        """
        Remove clearly unsupported real-time behavior when the original
        requirements do not contain real-time behavior.
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

        if allows_realtime:
            return

        architecture.data_flow = [
            ArchitectureQualityController._remove_realtime(
                value
            )
            for value in architecture.data_flow
        ]

        architecture.architectural_assumptions = [
            ArchitectureQualityController._remove_realtime(
                value
            )
            for value in architecture.architectural_assumptions
        ]

        architecture.components = [
            component.model_copy(
                update={
                    "name": ArchitectureQualityController._remove_realtime(
                        component.name
                    ),
                    "responsibility": (
                        ArchitectureQualityController._remove_realtime(
                            component.responsibility
                        )
                    ),
                }
            )
            for component in architecture.components
        ]

        architecture.architecture_decisions = [
            decision.model_copy(
                update={
                    "decision": ArchitectureQualityController._remove_realtime(
                        decision.decision
                    ),
                    "rationale": (
                        ArchitectureQualityController._remove_realtime(
                            decision.rationale
                        )
                    ),
                }
            )
            for decision in architecture.architecture_decisions
        ]

    @staticmethod
    def _remove_realtime(
        value: str,
    ) -> str:
        import re

        value = re.sub(
            r"\breal[- ]time\b\s*",
            "",
            value,
            flags=re.IGNORECASE,
        )

        value = re.sub(
            r"\brealtime\b\s*",
            "",
            value,
            flags=re.IGNORECASE,
        )

        value = re.sub(
            r"\s{2,}",
            " ",
            value,
        )

        return value.strip()

    @classmethod
    def _normalize_external_integrations(
        cls,
        architecture: SystemArchitecture,
    ) -> None:
        """
        Repair deterministic integration mismatches without triggering another
        full LLM generation.
        """
        if architecture.external_integrations:
            return

        text = cls._build_external_context(
            architecture
        )

        payment_indicators = (
            "payment gateway",
            "external payment service",
            "external payment processing service",
            "third-party payment",
        )

        generic_external_indicators = (
            "external service",
            "third-party service",
        )

        negative_external_phrases = (
            "no external service",
            "no external payment service",
            "no payment gateway",
            "without an external service",
            "without external service",
            "does not require an external service",
            "does not require external service",
            "does not require a payment gateway",
            "does not use an external service",
            "does not use external service",
        )

        if any(
            phrase in text
            for phrase in negative_external_phrases
        ):
            return

        if any(
            indicator in text
            for indicator in payment_indicators
        ):
            architecture.external_integrations.append(
                "External payment processing service"
            )
            return

        if any(
            indicator in text
            for indicator in generic_external_indicators
        ):
            architecture.external_integrations.append(
                "External third-party service"
            )

    @classmethod
    def _check_external_integrations(
        cls,
        architecture: SystemArchitecture,
    ) -> None:
        text = cls._build_external_context(
            architecture
        )

        integration_keywords = (
            "external payment service",
            "external payment processing service",
            "payment gateway",
            "third-party payment",
            "external service",
            "third-party service",
        )

        negative_external_phrases = (
            "no external service",
            "no external payment service",
            "no payment gateway",
            "without an external service",
            "without external service",
            "does not require an external service",
            "does not require external service",
            "does not require a payment gateway",
            "does not use an external service",
            "does not use external service",
        )

        mentions_external = any(
            keyword in text
            for keyword in integration_keywords
        )

        explicitly_not_external = any(
            phrase in text
            for phrase in negative_external_phrases
        )

        if (
            mentions_external
            and not explicitly_not_external
            and not architecture.external_integrations
        ):
            raise ValueError(
                "Architecture contains a confirmed external integration "
                "but external_integrations is empty."
            )

    @staticmethod
    def _check_architecture_consistency(
        architecture: SystemArchitecture,
    ) -> None:
        style = architecture.architecture_style.casefold()

        component_text = " ".join(
            component.name.casefold()
            for component in architecture.components
        )

        decision_text = " ".join(
            decision.decision.casefold()
            for decision in architecture.architecture_decisions
        )

        if (
            ("layered" in style or "modular monolith" in style)
            and (
                "microservice" in component_text
                or "microservice" in decision_text
            )
        ):
            raise ValueError(
                "Architecture style conflicts with "
                "microservice-based design."
            )