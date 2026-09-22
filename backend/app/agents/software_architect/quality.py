from collections import Counter

from app.core.traceability.requirements import RequirementRegistry

from app.agents.project_planner.schemas import ProjectPlan
from app.agents.requirement_analyst.schemas import RequirementAnalysis

from .schemas import SystemArchitecture


class ArchitectureQualityController:
    """
    Deterministic validation and normalization for SystemArchitecture.

    This controller validates structure, traceability, coverage, and
    cross-field consistency.

    It does not invent requirements or silently rewrite architectural text.
    """

    def validate(
        self,
        architecture: SystemArchitecture,
        requirements: RequirementAnalysis,
        project_plan: ProjectPlan,
        registry: RequirementRegistry,
    ) -> SystemArchitecture:

        self._check_project_name(
            architecture,
            requirements,
        )

        self._normalize_requirement_references(
            architecture,
            registry,
        )

        self._check_required_fields(
            architecture,
        )

        self._check_component_references(
            architecture,
            registry,
        )

        self._check_api_references(
            architecture,
            registry,
        )

        self._check_decision_references(
            architecture,
            registry,
        )

        self._check_component_coverage(
            architecture,
            registry,
        )

        self._check_duplicates(
            architecture,
        )

        self._normalize_external_integrations(
            architecture,
        )

        self._check_external_integrations(
            architecture,
        )

        self._check_unsupported_realtime_behavior(
            architecture,
            requirements,
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
    def _normalize_requirement_references(
        architecture: SystemArchitecture,
        registry: RequirementRegistry,
    ) -> None:
        """
        Convert legacy exact-text references into canonical IDs.

        No semantic rewriting is performed.
        """

        for component in architecture.components:
            component.related_requirements = (
                registry.normalize_references(
                    component.related_requirements
                )
            )

        for endpoint in architecture.api_endpoints:
            endpoint.related_requirements = (
                registry.normalize_references(
                    endpoint.related_requirements
                )
            )

        for decision in architecture.architecture_decisions:
            decision.related_requirements = (
                registry.normalize_references(
                    decision.related_requirements
                )
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
            if not value.strip():
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
        registry: RequirementRegistry,
    ) -> None:

        valid_ids = set(
            registry.ids
        )

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

            unknown_ids = (
                set(component.related_requirements)
                - valid_ids
            )

            if unknown_ids:
                raise ValueError(
                    f"Architecture component '{component.name}' "
                    f"references unknown requirements: "
                    f"{sorted(unknown_ids)}"
                )

    @staticmethod
    def _check_api_references(
        architecture: SystemArchitecture,
        registry: RequirementRegistry,
    ) -> None:

        valid_ids = set(
            registry.ids
        )

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

            unknown_ids = (
                set(endpoint.related_requirements)
                - valid_ids
            )

            if unknown_ids:
                raise ValueError(
                    f"API capability '{endpoint.name}' "
                    f"references unknown requirements: "
                    f"{sorted(unknown_ids)}"
                )

    @staticmethod
    def _check_decision_references(
        architecture: SystemArchitecture,
        registry: RequirementRegistry,
    ) -> None:

        valid_ids = set(
            registry.ids
        )

        for decision in architecture.architecture_decisions:

            if not decision.decision.strip():
                raise ValueError(
                    "Architecture decision cannot be empty."
                )

            if not decision.rationale.strip():
                raise ValueError(
                    f"Architecture decision '{decision.decision}' "
                    "must have a rationale."
                )

            if not decision.related_requirements:
                raise ValueError(
                    f"Architecture decision '{decision.decision}' "
                    "must reference at least one requirement."
                )

            unknown_ids = (
                set(decision.related_requirements)
                - valid_ids
            )

            if unknown_ids:
                raise ValueError(
                    f"Architecture decision '{decision.decision}' "
                    f"references unknown requirements: "
                    f"{sorted(unknown_ids)}"
                )

    @staticmethod
    def _check_component_coverage(
        architecture: SystemArchitecture,
        registry: RequirementRegistry,
    ) -> None:

        covered_ids = {
            requirement_id
            for component in architecture.components
            for requirement_id in component.related_requirements
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
                "System architecture does not contain a component "
                "covering every functional requirement. Missing: "
                f"{missing_details}"
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
            for name, count in Counter(
                component_names
            ).items()
            if count > 1
        ]

        if duplicate_components:
            raise ValueError(
                "Duplicate architecture components found: "
                f"{duplicate_components}"
            )

        endpoint_names = [
            endpoint.name.strip().casefold()
            for endpoint in architecture.api_endpoints
        ]

        duplicate_endpoints = [
            name
            for name, count in Counter(
                endpoint_names
            ).items()
            if count > 1
        ]

        if duplicate_endpoints:
            raise ValueError(
                "Duplicate API capabilities found: "
                f"{duplicate_endpoints}"
            )

    @staticmethod
    def _build_external_context(
        architecture: SystemArchitecture,
    ) -> str:

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

    @classmethod
    def _normalize_external_integrations(
        cls,
        architecture: SystemArchitecture,
    ) -> None:
        """
        Perform only safe field synchronization.

        If the generated architecture already explicitly states an external
        service, copy that same concept into external_integrations.

        This is not semantic invention.
        """

        if architecture.external_integrations:
            return

        text = cls._build_external_context(
            architecture
        )

        exact_integrations = (
            (
                "external payment processing service",
                "External payment processing service",
            ),
            (
                "external payment service",
                "External payment processing service",
            ),
            (
                "payment gateway",
                "Payment gateway",
            ),
            (
                "third-party payment",
                "Third-party payment service",
            ),
            (
                "third-party service",
                "External third-party service",
            ),
            (
                "external service",
                "External service",
            ),
        )

        for phrase, normalized_value in exact_integrations:
            if phrase in text:
                architecture.external_integrations.append(
                    normalized_value
                )
                return

    @classmethod
    def _check_external_integrations(
        cls,
        architecture: SystemArchitecture,
    ) -> None:

        text = cls._build_external_context(
            architecture
        )

        integration_keywords = (
            "external payment processing service",
            "external payment service",
            "payment gateway",
            "third-party payment",
            "third-party service",
            "external service",
        )

        mentions_external = any(
            keyword in text
            for keyword in integration_keywords
        )

        if (
            mentions_external
            and not architecture.external_integrations
        ):
            raise ValueError(
                "Architecture contains an external integration "
                "but external_integrations is empty."
            )

    @staticmethod
    def _check_unsupported_realtime_behavior(
        architecture: SystemArchitecture,
        requirements: RequirementAnalysis,
    ) -> None:

        requirement_text = " ".join(
            requirements.functional_requirements
        ).casefold()

        requires_realtime = (
            "real-time" in requirement_text
            or "real time" in requirement_text
            or "realtime" in requirement_text
        )

        if requires_realtime:
            return

        architecture_text = " ".join(
            [
                *architecture.data_flow,
                *architecture.architectural_assumptions,
                *[
                    component.responsibility
                    for component in architecture.components
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

        realtime_terms = (
            "real-time",
            "real time",
            "realtime",
        )

        detected = [
            term
            for term in realtime_terms
            if term in architecture_text
        ]

        if detected:
            raise ValueError(
                "Architecture introduces real-time behavior that is not "
                "present in the authoritative functional requirements: "
                f"{detected}"
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