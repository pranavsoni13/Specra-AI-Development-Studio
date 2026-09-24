from app.core.traceability.requirements import RequirementRegistry

from app.agents.project_planner.schemas import ProjectPlan
from app.agents.requirement_analyst.schemas import RequirementAnalysis

from .schemas import SystemArchitecture


class ArchitectureQualityController:
    """
    Deterministic validation for architecture artifacts.

    This layer validates:
    - structural correctness
    - requirement traceability
    - cross-field consistency
    - unsupported capability introduction

    It does not rewrite semantic model output.
    """

    def validate(
        self,
        architecture: SystemArchitecture,
        requirements: RequirementAnalysis,
        project_plan: ProjectPlan,
        registry: RequirementRegistry,
    ) -> SystemArchitecture:

        if not isinstance(architecture, SystemArchitecture):
            raise TypeError(
                "architecture must be an instance of SystemArchitecture."
            )

        if not isinstance(requirements, RequirementAnalysis):
            raise TypeError(
                "requirements must be an instance of RequirementAnalysis."
            )

        if not isinstance(project_plan, ProjectPlan):
            raise TypeError(
                "project_plan must be an instance of ProjectPlan."
            )

        self._validate_project_name(
            architecture=architecture,
            requirements=requirements,
        )

        self._normalize_requirement_references(
            architecture=architecture,
            registry=registry,
        )

        self._validate_components(architecture)
        self._validate_api_endpoints(architecture)
        self._validate_architecture_decisions(architecture)

        self._check_component_coverage(
            architecture=architecture,
            registry=registry,
        )

        self._check_api_coverage(
            architecture=architecture,
            registry=registry,
        )

        self._check_external_integrations(
            architecture=architecture,
            requirements=requirements,
        )

        self._check_unsupported_capabilities(
            architecture=architecture,
            requirements=requirements,
        )

        self._check_unsupported_realtime_behavior(
            architecture=architecture,
            requirements=requirements,
        )

        self._check_architecture_style_consistency(
            architecture=architecture,
        )

        return architecture

    def _validate_project_name(
        self,
        architecture: SystemArchitecture,
        requirements: RequirementAnalysis,
    ) -> None:

        if architecture.project_name.strip() != requirements.project_name.strip():
            raise ValueError(
                "Architecture project_name does not match the requirement analysis."
            )

    def _normalize_requirement_references(
        self,
        architecture: SystemArchitecture,
        registry: RequirementRegistry,
    ) -> None:

        for component in architecture.components:
            component.related_requirements = registry.normalize_references(
                component.related_requirements
            )

        for endpoint in architecture.api_endpoints:
            endpoint.related_requirements = registry.normalize_references(
                endpoint.related_requirements
            )

        for decision in architecture.architecture_decisions:
            decision.related_requirements = registry.normalize_references(
                decision.related_requirements
            )

    def _validate_components(
        self,
        architecture: SystemArchitecture,
    ) -> None:

        if not architecture.components:
            raise ValueError(
                "Architecture must contain at least one component."
            )

        seen_names: set[str] = set()

        for component in architecture.components:
            name = component.name.strip()

            if not name:
                raise ValueError(
                    "Architecture component name cannot be empty."
                )

            if not component.responsibility.strip():
                raise ValueError(
                    f"Architecture component '{name}' has an empty responsibility."
                )

            if not component.related_requirements:
                raise ValueError(
                    f"Architecture component '{name}' has no requirement references."
                )

            normalized_name = self._normalize_text(name)

            if normalized_name in seen_names:
                raise ValueError(
                    f"Duplicate architecture component detected: '{name}'."
                )

            seen_names.add(normalized_name)

    def _validate_api_endpoints(
        self,
        architecture: SystemArchitecture,
    ) -> None:

        if not architecture.api_endpoints:
            raise ValueError(
                "Architecture must contain at least one API endpoint or API capability."
            )

        seen_names: set[str] = set()

        for endpoint in architecture.api_endpoints:
            name = endpoint.name.strip()

            if not name:
                raise ValueError(
                    "API endpoint name cannot be empty."
                )

            if not endpoint.purpose.strip():
                raise ValueError(
                    f"API endpoint '{name}' has an empty purpose."
                )

            if not endpoint.related_requirements:
                raise ValueError(
                    f"API endpoint '{name}' has no requirement references."
                )

            normalized_name = self._normalize_text(name)

            if normalized_name in seen_names:
                raise ValueError(
                    f"Duplicate API endpoint detected: '{name}'."
                )

            seen_names.add(normalized_name)

    def _validate_architecture_decisions(
        self,
        architecture: SystemArchitecture,
    ) -> None:

        if not architecture.architecture_decisions:
            raise ValueError(
                "Architecture must contain at least one architecture decision."
            )

        for decision in architecture.architecture_decisions:
            if not decision.decision.strip():
                raise ValueError(
                    "Architecture decision cannot be empty."
                )

            if not decision.rationale.strip():
                raise ValueError(
                    f"Architecture decision '{decision.decision}' has an empty rationale."
                )

            if not decision.related_requirements:
                raise ValueError(
                    f"Architecture decision '{decision.decision}' has no requirement references."
                )

    def _check_component_coverage(
        self,
        architecture: SystemArchitecture,
        registry: RequirementRegistry,
    ) -> None:

        covered_requirements: set[str] = set()

        for component in architecture.components:
            covered_requirements.update(
                component.related_requirements
            )

        missing = [
            requirement_id
            for requirement_id in registry.ids
            if requirement_id not in covered_requirements
        ]

        if missing:
            raise ValueError(
                "The following functional requirements are not covered by "
                f"any architecture component: {', '.join(missing)}"
            )

    def _check_api_coverage(
        self,
        architecture: SystemArchitecture,
        registry: RequirementRegistry,
    ) -> None:

        covered_requirements: set[str] = set()

        for endpoint in architecture.api_endpoints:
            covered_requirements.update(
                endpoint.related_requirements
            )

        missing = [
            requirement_id
            for requirement_id in registry.ids
            if requirement_id not in covered_requirements
        ]

        if missing:
            raise ValueError(
                "The following functional requirements are not represented "
                f"by any API endpoint: {', '.join(missing)}"
            )

    def _check_external_integrations(
        self,
        architecture: SystemArchitecture,
        requirements: RequirementAnalysis,
    ) -> None:

        requirement_text = " ".join(
            requirements.functional_requirements
        ).casefold()

        architecture_text = " ".join(
            [
                architecture.authentication,
                *[
                    component.responsibility
                    for component in architecture.components
                ],
                *[
                    endpoint.purpose
                    for endpoint in architecture.api_endpoints
                ],
                *architecture.data_flow,
                *architecture.architectural_assumptions,
            ]
        ).casefold()

        payment_requested = any(
            term in requirement_text
            for term in (
                "payment",
                "payments",
                "pay",
                "checkout",
            )
        )

        payment_mentioned = any(
            term in architecture_text
            for term in (
                "payment service",
                "payment processing service",
                "external payment",
                "payment gateway",
                "payment processor",
            )
        )

        if payment_requested and payment_mentioned:
            has_payment_integration = any(
                any(
                    payment_term in integration.casefold()
                    for payment_term in (
                        "payment",
                        "payment processor",
                        "payment gateway",
                    )
                )
                for integration in architecture.external_integrations
            )

            if not has_payment_integration:
                architecture.external_integrations.append(
                    "External payment processing service"
                )

    def _check_unsupported_capabilities(
        self,
        architecture: SystemArchitecture,
        requirements: RequirementAnalysis,
    ) -> None:
        """
        Detect clear capabilities introduced by the architecture that are
        not supported by the authoritative requirements.

        This intentionally uses a small conservative set of high-confidence
        checks rather than broad semantic rewriting.
        """

        requirement_text = " ".join(
            [
                requirements.objective,
                *requirements.functional_requirements,
                *requirements.non_functional_requirements,
            ]
        ).casefold()

        component_text = " ".join(
            [
                component.name
                for component in architecture.components
            ]
            + [
                component.responsibility
                for component in architecture.components
            ]
        ).casefold()

        endpoint_text = " ".join(
            [
                endpoint.name
                for endpoint in architecture.api_endpoints
            ]
            + [
                endpoint.purpose
                for endpoint in architecture.api_endpoints
            ]
        ).casefold()

        architecture_text = " ".join(
            [
                architecture.authentication,
                architecture.data_flow,
                architecture.external_integrations,
                architecture.architectural_assumptions,
            ]
            + [
                decision.decision
                for decision in architecture.architecture_decisions
            ]
            + [
                decision.rationale
                for decision in architecture.architecture_decisions
            ]
        ).casefold()

        full_text = " ".join(
            [
                component_text,
                endpoint_text,
                architecture_text,
            ]
        )

        authentication_required = any(
            term in requirement_text
            for term in (
                "authentication",
                "authenticate",
                "login",
                "log in",
                "signup",
                "sign up",
                "user account",
                "accounts",
                "authorization",
                "authorisation",
            )
        )

        if not authentication_required:
            unsupported_auth_terms = (
                "token-based authentication",
                "token based authentication",
                "jwt authentication",
                "jwt",
                "oauth",
                "login",
                "log in",
                "signup",
                "sign up",
                "authentication service",
                "authorization service",
                "authorisation service",
            )

            found_auth_terms = [
                term
                for term in unsupported_auth_terms
                if term in full_text
            ]

            if found_auth_terms:
                raise ValueError(
                    "Architecture introduces authentication behavior that is "
                    "not supported by the requirements: "
                    + ", ".join(sorted(set(found_auth_terms)))
                )

        discovery_requirement = any(
            term in requirement_text
            for term in (
                "discover restaurants",
                "restaurant discovery",
                "browse restaurants",
            )
        )

        if discovery_requirement:
            unsupported_discovery_terms = (
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

            found_discovery_terms = [
                term
                for term in unsupported_discovery_terms
                if term in full_text
            ]

            if found_discovery_terms:
                raise ValueError(
                    "Architecture introduces unsupported restaurant-discovery "
                    "capabilities: "
                    + ", ".join(sorted(set(found_discovery_terms)))
                )

    def _check_unsupported_realtime_behavior(
        self,
        architecture: SystemArchitecture,
        requirements: RequirementAnalysis,
    ) -> None:

        requirement_text = " ".join(
            requirements.functional_requirements
        ).casefold()

        architecture_text = " ".join(
            [
                architecture.frontend,
                architecture.backend,
                architecture.database,
                architecture.authentication,
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
                *architecture.data_flow,
                *architecture.external_integrations,
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

        if realtime_required:
            return

        unsupported_terms = (
            "real-time",
            "realtime",
            "websocket",
            "web sockets",
            "live gps",
            "gps tracking",
            "push notification",
            "push notifications",
        )

        found_terms = [
            term
            for term in unsupported_terms
            if term in architecture_text
        ]

        if found_terms:
            unique_terms = sorted(set(found_terms))

            raise ValueError(
                "Architecture introduces unsupported real-time or advanced "
                f"tracking behavior: {', '.join(unique_terms)}"
            )

    def _check_architecture_style_consistency(
        self,
        architecture: SystemArchitecture,
    ) -> None:

        if not architecture.architecture_style.strip():
            raise ValueError(
                "Architecture style cannot be empty."
            )

        if not architecture.frontend.strip():
            raise ValueError(
                "Frontend architecture cannot be empty."
            )

        if not architecture.backend.strip():
            raise ValueError(
                "Backend architecture cannot be empty."
            )

        if not architecture.database.strip():
            raise ValueError(
                "Database architecture cannot be empty."
            )

        if not architecture.authentication.strip():
            raise ValueError(
                "Authentication architecture cannot be empty."
            )

        if not architecture.data_flow:
            raise ValueError(
                "Architecture must contain at least one data-flow description."
            )

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join(value.split()).casefold()