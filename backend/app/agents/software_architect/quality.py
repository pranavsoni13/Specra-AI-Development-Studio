from collections import Counter
import re

from app.core.traceability.requirements import RequirementRegistry

from app.agents.project_planner.schemas import ProjectPlan
from app.agents.requirement_analyst.schemas import RequirementAnalysis

from .schemas import SystemArchitecture


class ArchitectureQualityController:
    """
    Deterministic validation for SystemArchitecture.

    Structural and traceability rules are enforced here so they do not
    depend on the local model noticing every contradiction.
    """

    def validate(
        self,
        architecture: SystemArchitecture,
        requirements: RequirementAnalysis,
        project_plan: ProjectPlan,
        registry: RequirementRegistry | None = None,
    ) -> SystemArchitecture:
        if not isinstance(architecture, SystemArchitecture):
            raise TypeError("architecture must be a SystemArchitecture object.")

        if registry is None:
            registry = RequirementRegistry.from_analysis(requirements)

        self._check_project_name(architecture, requirements)
        self._check_required_fields(architecture)
        self._normalize_requirement_references(architecture, registry)
        self._check_component_references(architecture, registry)
        self._check_api_references(architecture, registry)
        self._check_architecture_decisions(architecture, requirements, registry)
        self._check_requirement_coverage(architecture, registry)
        self._check_duplicates(architecture)
        self._normalize_external_integrations(architecture)
        self._check_external_integrations(architecture)
        self._check_authentication_consistency(architecture, requirements)
        self._check_unsupported_realtime_behavior(architecture, requirements)
        self._check_architecture_consistency(architecture)

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
            raise ValueError("Architecture must contain at least one component.")

        if not architecture.data_flow:
            raise ValueError(
                "Architecture must contain at least one data-flow statement."
            )

        if not architecture.architecture_decisions:
            raise ValueError(
                "Architecture must contain at least one architecture decision."
            )

    @staticmethod
    def _normalize_requirement_references(
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

    @staticmethod
    def _check_component_references(
        architecture: SystemArchitecture,
        registry: RequirementRegistry,
    ) -> None:
        for component in architecture.components:
            if not component.name.strip():
                raise ValueError("Architecture component name cannot be empty.")

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

            registry.validate_references(component.related_requirements)

    @staticmethod
    def _check_api_references(
        architecture: SystemArchitecture,
        registry: RequirementRegistry,
    ) -> None:
        for endpoint in architecture.api_endpoints:
            if not endpoint.name.strip():
                raise ValueError("API capability name cannot be empty.")

            if not endpoint.purpose.strip():
                raise ValueError(
                    f"API capability '{endpoint.name}' must have a purpose."
                )

            if not endpoint.related_requirements:
                raise ValueError(
                    f"API capability '{endpoint.name}' "
                    "must reference at least one requirement."
                )

            registry.validate_references(endpoint.related_requirements)

    @staticmethod
    def _check_architecture_decisions(
        architecture: SystemArchitecture,
        requirements: RequirementAnalysis,
        registry: RequirementRegistry,
    ) -> None:
        explicit_claim_phrases = (
            "explicitly stated",
            "explicitly required",
            "requirements require",
            "requirements explicitly",
            "requirement requires",
            "required by the requirements",
            "required by requirements",
            "user requested",
            "user explicitly requested",
            "mandated by the requirements",
            "specified by the requirements",
        )

        authentication_terms = (
            "authentication",
            "authenticate",
            "login",
            "log in",
            "sign in",
            "signin",
            "authorization",
            "authorisation",
            "password",
            "credentials",
            "access control",
            "jwt",
            "oauth",
        )

        authentication_requirement_keywords = authentication_terms + (
            "account",
            "identity",
            "protected data",
        )

        requirement_text_by_id = {
            requirement_id: registry.text_for_id(requirement_id).casefold()
            for requirement_id in registry.ids
        }

        for decision in architecture.architecture_decisions:
            if not decision.decision.strip():
                raise ValueError("Architecture decision cannot be empty.")

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

            registry.validate_references(decision.related_requirements)

            decision_text = (
                f"{decision.decision} {decision.rationale}".casefold()
            )

            references_authentication = any(
                term in decision_text
                for term in authentication_terms
            )

            if not references_authentication:
                continue

            referenced_requirement_text = " ".join(
                requirement_text_by_id[requirement_id]
                for requirement_id in decision.related_requirements
            )

            supports_authentication_claim = any(
                term in referenced_requirement_text
                for term in authentication_requirement_keywords
            )

            unsupported_negative_claim = any(
                phrase in decision_text
                for phrase in (
                    "no authentication required",
                    "authentication not required",
                    "authentication is not required",
                    "no need for authentication",
                    "authentication is unnecessary",
                )
            )

            claims_explicit_support = any(
                phrase in decision_text
                for phrase in explicit_claim_phrases
            )

            if (
                (claims_explicit_support or unsupported_negative_claim)
                and not supports_authentication_claim
            ):
                raise ValueError(
                    "Architecture decision makes an unsupported authentication "
                    "requirement claim. The referenced requirements do not "
                    "establish authentication, and absence of an authentication "
                    "requirement must not be presented as an explicit negative "
                    "requirement."
                )

    @staticmethod
    def _check_requirement_coverage(
        architecture: SystemArchitecture,
        registry: RequirementRegistry,
    ) -> None:
        covered = set()

        for component in architecture.components:
            covered.update(component.related_requirements)

        missing = [
            requirement_id
            for requirement_id in registry.ids
            if requirement_id not in covered
        ]

        if missing:
            raise ValueError(
                "Architecture is missing component coverage for functional "
                f"requirements: {missing}"
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
                f"Duplicate architecture components found: {duplicate_components}"
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
                f"Duplicate API capabilities found: {duplicate_endpoints}"
            )

        decision_keys = [
            decision.decision.strip().casefold()
            for decision in architecture.architecture_decisions
        ]

        duplicate_decisions = [
            value
            for value, count in Counter(decision_keys).items()
            if count > 1
        ]

        if duplicate_decisions:
            raise ValueError(
                f"Duplicate architecture decisions found: {duplicate_decisions}"
            )

    @staticmethod
    def _build_architecture_text(
        architecture: SystemArchitecture,
    ) -> str:
        return " ".join(
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

    @classmethod
    def _normalize_external_integrations(
        cls,
        architecture: SystemArchitecture,
    ) -> None:
        if architecture.external_integrations:
            return

        text = cls._build_architecture_text(architecture)

        negative_phrases = (
            "no external service",
            "no external payment service",
            "no payment gateway",
            "without an external service",
            "without external service",
            "does not require an external service",
            "does not require external service",
            "does not require a payment gateway",
            "not required based on current requirements",
        )

        if any(phrase in text for phrase in negative_phrases):
            return

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

        if any(indicator in text for indicator in payment_indicators):
            architecture.external_integrations.append(
                "External payment processing service"
            )
            return

        if any(indicator in text for indicator in generic_external_indicators):
            architecture.external_integrations.append(
                "External third-party service"
            )

    @classmethod
    def _check_external_integrations(
        cls,
        architecture: SystemArchitecture,
    ) -> None:
        text = cls._build_architecture_text(architecture)

        positive_terms = (
            "external payment service",
            "external payment processing service",
            "payment gateway",
            "third-party payment",
            "external service",
            "third-party service",
        )

        negative_phrases = (
            "no external service",
            "no external payment service",
            "no payment gateway",
            "without an external service",
            "without external service",
            "does not require an external service",
            "does not require external service",
            "does not require a payment gateway",
            "not required based on current requirements",
        )

        mentions_external = any(term in text for term in positive_terms)
        explicitly_not_external = any(
            phrase in text for phrase in negative_phrases
        )

        if mentions_external and not explicitly_not_external and not architecture.external_integrations:
            raise ValueError(
                "Architecture contains a confirmed external integration "
                "but external_integrations is empty."
            )

    @staticmethod
    def _check_authentication_consistency(
        architecture: SystemArchitecture,
        requirements: RequirementAnalysis,
    ) -> None:
        requirement_text = " ".join(
            [
                requirements.objective,
                *requirements.functional_requirements,
                *requirements.non_functional_requirements,
                *requirements.constraints,
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
                "credentials",
                "access control",
                "account",
                "identity",
                "protected data",
            )
        )

        selected = architecture.authentication.strip().casefold()
        explicit_none_values = {
            "none",
            "not required",
            "not required based on current requirements",
            "no authentication",
            "no authentication required",
        }

        selected_positive = selected not in explicit_none_values

        if authentication_required and not selected_positive:
            raise ValueError(
                "Authentication-related requirements are present, but "
                "SystemArchitecture does not provide an authentication approach."
            )

        if not authentication_required and selected_positive:
            assumption_text = " ".join(
                architecture.architectural_assumptions
            ).casefold()

            if "authentication" not in assumption_text and not any(
                term in assumption_text
                for term in ("login", "sign in", "credentials", "authorization")
            ):
                raise ValueError(
                    "SystemArchitecture introduces a positive authentication "
                    "approach without an explicit authentication requirement "
                    "or a clearly labeled architectural assumption."
                )

    @staticmethod
    def _architecture_text_fields(
        architecture: SystemArchitecture,
    ) -> list[tuple[str, str]]:
        """Return individually labeled artifact fields for explainable checks."""
        fields: list[tuple[str, str]] = [
            ("architecture_style", architecture.architecture_style),
            ("frontend", architecture.frontend),
            ("backend", architecture.backend),
            ("database", architecture.database),
            ("authentication", architecture.authentication),
        ]
        fields.extend(
            (f"data_flow[{index}]", value)
            for index, value in enumerate(architecture.data_flow)
        )
        fields.extend(
            (f"external_integrations[{index}]", value)
            for index, value in enumerate(architecture.external_integrations)
        )
        fields.extend(
            (f"architectural_assumptions[{index}]", value)
            for index, value in enumerate(architecture.architectural_assumptions)
        )
        fields.extend(
            (f"components[{index}].name", component.name)
            for index, component in enumerate(architecture.components)
        )
        fields.extend(
            (f"components[{index}].responsibility", component.responsibility)
            for index, component in enumerate(architecture.components)
        )
        fields.extend(
            (f"api_endpoints[{index}].name", endpoint.name)
            for index, endpoint in enumerate(architecture.api_endpoints)
        )
        fields.extend(
            (f"api_endpoints[{index}].purpose", endpoint.purpose)
            for index, endpoint in enumerate(architecture.api_endpoints)
        )
        fields.extend(
            (f"architecture_decisions[{index}].decision", decision.decision)
            for index, decision in enumerate(architecture.architecture_decisions)
        )
        fields.extend(
            (f"architecture_decisions[{index}].rationale", decision.rationale)
            for index, decision in enumerate(architecture.architecture_decisions)
        )
        return fields

    @staticmethod
    def _is_negated_capability_mention(
        text: str,
        term: str,
        start: int,
        end: int,
    ) -> bool:
        """Distinguish a statement rejecting a capability from adding it.

        The check is deliberately local to the phrase: a negative word far
        away in a different clause must not excuse a positive capability.
        """
        before_words = re.findall(r"[\w'-]+", text[:start].casefold())[-6:]
        after_words = re.findall(r"[\w'-]+", text[end:].casefold())[:6]
        negation_markers = {
            "no", "not", "never", "without", "avoid", "avoids", "avoided",
            "exclude", "excluded", "excluding", "omit", "omitted",
            "unsupported", "unrequested", "unneeded", "unnecessary",
            "outside", "isn't", "aren't", "wasn't", "weren't", "doesn't",
            "don't", "didn't", "cannot", "can't", "won't", "shouldn't",
            "mustn't",
        }

        before_is_negative = any(word in negation_markers for word in before_words)
        after_is_negative = any(word in negation_markers for word in after_words)

        # "not only X" is not a negation of X.
        if len(before_words) >= 2 and before_words[-2:] == ["not", "only"]:
            before_is_negative = False

        nearby = " ".join(before_words + [term.casefold()] + after_words)
        negative_phrases = (
            "out of scope", "not in scope", "not required", "not needed",
            "not included", "not implemented", "not supported", "not requested",
            "not necessary", "not a requirement", "not part of the scope",
            "will not be", "will not include", "will not implement",
            "should not be", "must not be", "does not include",
            "does not support", "do not include", "do not support",
            "is not enabled", "is not provided", "are not enabled",
        )
        phrase_is_negative = any(phrase in nearby for phrase in negative_phrases)
        return before_is_negative or after_is_negative or phrase_is_negative

    @staticmethod
    def _is_speculative_tracking_assumption(
        text: str,
        start: int,
        end: int,
    ) -> bool:
        """Return True only for explicitly modal, unresolved assumption text.

        This does not excuse a selected feature. It distinguishes phrases such
        as "may require real-time tracking" inside architectural_assumptions
        from an implemented capability. The reviewer must surface such
        speculation as an unresolved low-severity assumption.
        """
        prefix = text[max(0, start - 100):start].casefold()
        clause = re.split(r"[.;\n]", prefix)[-1]
        modal_dependency = re.search(
            r"\b(?:may|might|could|possibly|potentially)\s+"
            r"(?:also\s+)?(?:require|need|involve|depend on)\b",
            clause,
        )
        modal_need = re.search(
            r"\b(?:may|might|could)\s+(?:be\s+)?needed\b",
            clause,
        )
        return bool(modal_dependency or modal_need)

    @classmethod
    def _positive_unsupported_tracking_mentions(
        cls,
        architecture: SystemArchitecture,
    ) -> list[str]:
        unsupported_terms = (
            "real-time", "realtime", "websocket", "web sockets",
            "gps tracking", "live gps", "live location", "location tracking",
            "push notification", "push notifications", "live updates",
            "instant updates", "continuous location",
        )
        findings: list[str] = []
        for field_name, value in cls._architecture_text_fields(architecture):
            text = value.casefold()
            for term in unsupported_terms:
                for match in re.finditer(re.escape(term), text):
                    if cls._is_negated_capability_mention(
                        text, term, match.start(), match.end()
                    ):
                        continue
                    if (
                        field_name.startswith("architectural_assumptions[")
                        and cls._is_speculative_tracking_assumption(
                            text, match.start(), match.end()
                        )
                    ):
                        continue
                    excerpt = " ".join(value.split())
                    if len(excerpt) > 150:
                        excerpt = excerpt[:147] + "..."
                    findings.append(
                        f"{field_name} contains '{term}' in '{excerpt}'"
                    )
                    break
        return findings

    @classmethod
    def _has_positive_term(
        cls,
        text: str,
        terms: tuple[str, ...],
    ) -> bool:
        normalized = text.casefold()
        for term in terms:
            for match in re.finditer(re.escape(term), normalized):
                if not cls._is_negated_capability_mention(
                    normalized, term, match.start(), match.end()
                ):
                    return True
        return False

    @classmethod
    def _check_unsupported_realtime_behavior(
        cls,
        architecture: SystemArchitecture,
        requirements: RequirementAnalysis,
    ) -> None:
        requirement_text = " ".join(
            [
                requirements.objective,
                *requirements.functional_requirements,
                *requirements.non_functional_requirements,
                *requirements.constraints,
            ]
        ).casefold()

        # Permission is feature-specific: asking for GPS does not implicitly
        # authorize push notifications, and asking for live updates does not
        # imply location tracking.
        capability_families = (
            (
                "live update cadence / transport",
                ("real-time", "realtime", "live updates", "instant updates", "websocket", "web sockets"),
            ),
            (
                "GPS / continuous location tracking",
                ("gps tracking", "live gps", "live location", "location tracking", "continuous location"),
            ),
            (
                "push notifications",
                ("push notification", "push notifications"),
            ),
        )

        terms_to_check: list[str] = []
        for _family_name, family_terms in capability_families:
            if not cls._has_positive_term(requirement_text, family_terms):
                terms_to_check.extend(family_terms)

        found: list[str] = []
        for field_name, value in cls._architecture_text_fields(architecture):
            text = value.casefold()
            for term in terms_to_check:
                for match in re.finditer(re.escape(term), text):
                    if cls._is_negated_capability_mention(
                        text, term, match.start(), match.end()
                    ):
                        continue
                    if (
                        field_name.startswith("architectural_assumptions[")
                        and cls._is_speculative_tracking_assumption(
                            text, match.start(), match.end()
                        )
                    ):
                        continue
                    excerpt = " ".join(value.split())
                    if len(excerpt) > 150:
                        excerpt = excerpt[:147] + "..."
                    found.append(
                        f"{field_name} contains '{term}' in '{excerpt}'"
                    )
                    break

        if found:
            raise ValueError(
                "Architecture contains positive unsupported tracking/update "
                "capability claims. Remove the capability or add a matching "
                "authoritative requirement. Offending fields: "
                + "; ".join(found)
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
            ("layered" in style or "modular monolith" in style or "monolithic" in style)
            and "microservice" in component_text
        ):
            raise ValueError(
                "Architecture style conflicts with microservice-based components."
            )

        if (
            ("layered" in style or "modular monolith" in style or "monolithic" in style)
            and "microservice" in decision_text
        ):
            raise ValueError(
                "Architecture style conflicts with a microservice architecture decision."
            )
