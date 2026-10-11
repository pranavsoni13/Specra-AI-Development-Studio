from collections import Counter
import re

from app.agents.project_planner.schemas import ProjectPlan
from app.agents.requirement_analyst.schemas import RequirementAnalysis
from app.agents.software_architect.schemas import SystemArchitecture
from app.core.traceability.requirements import RequirementRegistry
from app.core.traceability.requirement_polarity import authentication_policy

from .schemas import ReviewFinding, ReviewReport


class TechnicalReviewQualityController:
    """Deterministic validation for Technical Reviewer output."""

    def validate(
        self,
        report: ReviewReport,
        requirements: RequirementAnalysis,
        project_plan: ProjectPlan,
        architecture: SystemArchitecture,
        registry: RequirementRegistry | None = None,
    ) -> ReviewReport:
        if not isinstance(report, ReviewReport):
            raise TypeError("report must be an instance of ReviewReport.")
        registry = registry or RequirementRegistry.from_analysis(requirements)

        self._check_project_name(report, requirements)
        self._check_coverage(report, project_plan, architecture, registry)
        self._remove_auth_sentinel_false_positive(report, requirements, architecture)
        self._apply_deterministic_architecture_checks(
            report, requirements, architecture, registry
        )
        self._check_findings(report)
        self._synchronize_recommended_actions(report)
        self._check_status(report)
        self._check_problem_consistency(report)
        self._synchronize_summary(report)
        return report

    @classmethod
    def _remove_auth_sentinel_false_positive(
        cls,
        report: ReviewReport,
        requirements: RequirementAnalysis,
        architecture: SystemArchitecture,
    ) -> None:
        """Remove only the known false positive about the neutral auth sentinel.

        The sentinel is explicitly allowed by the architecture contract. This
        filter never applies when an architecture decision actually discusses
        authentication; provenance checks must still review those decisions.
        """
        sentinel = architecture.authentication.strip().casefold() in {
            "none",
            "not required",
            "not required based on current requirements",
            "no authentication",
            "no authentication required",
        }
        requirement_text = " ".join(
            [
                requirements.objective,
                *requirements.functional_requirements,
                *requirements.non_functional_requirements,
                *requirements.constraints,
            ]
        ).casefold()
        auth_terms = (
            "authentication", "authenticate", "login", "log in",
            "sign in", "signin", "authorization", "authorisation",
            "password", "credentials", "access control", "jwt", "oauth",
        )
        auth_is_explicit = any(term in requirement_text for term in auth_terms)
        decisions_mention_auth = any(
            any(term in f"{decision.decision} {decision.rationale}".casefold() for term in auth_terms)
            for decision in architecture.architecture_decisions
        )
        if not sentinel or auth_is_explicit or decisions_mention_auth:
            return

        retained = []
        removed_titles: set[str] = set()
        for finding in report.findings:
            title = finding.title.strip().casefold()
            evidence = finding.evidence.casefold()
            is_known_false_positive = (
                finding.severity == "low"
                and "authentication" in title
                and ("clarification" in title or "status" in title)
                and "not required based on current requirements" in evidence
            )
            if is_known_false_positive:
                removed_titles.add(title)
            else:
                retained.append(finding)
        if not removed_titles:
            return

        report.findings = retained
        report.unsupported_additions = [
            item for item in report.unsupported_additions
            if not ("authentication" in item.casefold() and ("clarification" in item.casefold() or "not explicitly mentioned" in item.casefold()))
        ]
        report.architecture_consistency_issues = [
            item for item in report.architecture_consistency_issues
            if not ("authentication" in item.casefold() and ("clarification" in item.casefold() or "not explicitly mentioned" in item.casefold()))
        ]
        report.recommended_actions = [
            item for item in report.recommended_actions
            if not ("authentication" in item.casefold() and ("clarify" in item.casefold() or "clarification" in item.casefold()))
        ]
        if (
            report.overall_status == "NEEDS_REVISION"
            and not report.findings
            and not report.unsupported_additions
            and not report.architecture_consistency_issues
        ):
            report.overall_status = "PASS"

    @staticmethod
    def _check_project_name(report: ReviewReport, requirements: RequirementAnalysis) -> None:
        if report.project_name.strip().casefold() != requirements.project_name.strip().casefold():
            raise ValueError(
                "Review report project_name does not match RequirementAnalysis project_name."
            )

    @staticmethod
    def _check_coverage(
        report: ReviewReport,
        project_plan: ProjectPlan,
        architecture: SystemArchitecture,
        registry: RequirementRegistry,
    ) -> None:
        required_ids = set(registry.ids)

        plan_refs: set[str] = set()
        for milestone in project_plan.milestones:
            milestone_refs = registry.normalize_references(milestone.requirement_refs)
            plan_refs.update(milestone_refs)
            for task in milestone.tasks:
                task_refs = registry.normalize_references(task.requirement_refs)
                if not set(task_refs).issubset(milestone_refs):
                    raise ValueError(
                        f"ProjectPlan task '{task.description}' contains requirement "
                        "references outside its parent milestone."
                    )
                plan_refs.update(task_refs)

        component_refs = {
            ref
            for component in architecture.components
            for ref in registry.normalize_references(component.related_requirements)
        }
        api_refs = {
            ref
            for endpoint in architecture.api_endpoints
            for ref in registry.normalize_references(endpoint.related_requirements)
        }

        seen: list[str] = []
        for coverage in report.requirement_coverage:
            requirement_id = registry.normalize_reference(coverage.requirement_id)
            seen.append(requirement_id)

            if coverage.requirement.strip() != registry.text_for_id(requirement_id).strip():
                raise ValueError(f"Requirement text mismatch for {requirement_id}.")
            if coverage.in_project_plan != (requirement_id in plan_refs):
                raise ValueError(f"Incorrect project-plan coverage for {requirement_id}.")
            if coverage.in_architecture != (requirement_id in component_refs):
                raise ValueError(f"Incorrect architecture coverage for {requirement_id}.")
            if coverage.in_api != (requirement_id in api_refs):
                raise ValueError(f"Incorrect API coverage for {requirement_id}.")

        duplicates = [x for x, n in Counter(seen).items() if n > 1]
        if duplicates:
            raise ValueError(f"Review report contains duplicate requirement coverage entries: {duplicates}")

        seen_set = set(seen)
        if missing := required_ids - seen_set:
            raise ValueError(f"Review report is missing requirement coverage entries: {sorted(missing)}")
        if extra := seen_set - required_ids:
            raise ValueError(f"Review report contains invalid requirement IDs: {sorted(extra)}")

    @staticmethod
    def _check_findings(report: ReviewReport) -> None:
        titles = [f.title.strip().casefold() for f in report.findings]
        if duplicates := [x for x, n in Counter(titles).items() if n > 1]:
            raise ValueError(f"Duplicate review findings found: {duplicates}")
        for finding in report.findings:
            if not finding.title.strip():
                raise ValueError("Review finding title cannot be empty.")
            if not finding.evidence.strip():
                raise ValueError(f"Review finding '{finding.title}' must contain evidence.")
            if not finding.recommendation.strip():
                raise ValueError(f"Review finding '{finding.title}' must contain a recommendation.")

    @classmethod
    def _apply_deterministic_architecture_checks(
        cls,
        report: ReviewReport,
        requirements: RequirementAnalysis,
        architecture: SystemArchitecture,
        registry: RequirementRegistry,
    ) -> None:
        requirement_text = " ".join(
            [
                requirements.objective,
                *requirements.functional_requirements,
                *requirements.non_functional_requirements,
                *requirements.constraints,
            ]
        ).casefold()
        authentication_required, authentication_prohibited = (
            authentication_policy(requirements)
        )
        cls._check_authentication(
            report,
            architecture,
            authentication_required,
            authentication_prohibited,
        )
        cls._check_authentication_provenance(report, architecture, registry)
        cls._check_realtime(report, requirement_text, architecture)
        cls._check_speculative_tracking_assumptions(
            report, requirement_text, architecture
        )
        cls._check_unresolved_integration_assumptions(report, architecture)
        cls._check_discovery_enrichment(report, requirement_text, architecture)
        cls._check_api_coverage(report, architecture, registry)

    @staticmethod
    def _architecture_text(architecture: SystemArchitecture) -> str:
        values = [
            architecture.architecture_style,
            architecture.frontend,
            architecture.backend,
            architecture.database,
            architecture.authentication,
            *architecture.data_flow,
            *architecture.external_integrations,
            *architecture.architectural_assumptions,
            *(c.name for c in architecture.components),
            *(c.responsibility for c in architecture.components),
            *(e.name for e in architecture.api_endpoints),
            *(e.purpose for e in architecture.api_endpoints),
            *(d.decision for d in architecture.architecture_decisions),
            *(d.rationale for d in architecture.architecture_decisions),
        ]
        return " ".join(values).casefold()

    @classmethod
    def _check_authentication(
        cls,
        report: ReviewReport,
        architecture: SystemArchitecture,
        required: bool,
        prohibited: bool,
    ) -> None:
        selected = architecture.authentication.strip().casefold()
        none_values = {
            "none",
            "not required",
            "not required based on current requirements",
            "no authentication",
            "no authentication required",
            "not applicable by scope",
        }
        selected_positive = bool(selected) and selected not in none_values

        if prohibited and selected_positive:
            cls._add_finding(
                report,
                ReviewFinding(
                    category="architecture",
                    severity="critical",
                    title="Authentication contradicts an explicit scope constraint",
                    evidence=(
                        "RequirementAnalysis explicitly prohibits authentication, "
                        f"but SystemArchitecture selects '{architecture.authentication}'."
                    ),
                    recommendation=(
                        "Remove authentication, login, credentials, authorization, "
                        "and identity-provider capabilities from the architecture."
                    ),
                ),
                "SystemArchitecture violates an explicit authentication prohibition.",
                "Authentication is an unsupported addition that conflicts with a scope constraint.",
                "Regenerate the architecture without authentication or identity-provider assumptions.",
            )
            return

        if required and selected in none_values:
            cls._add_finding(
                report,
                ReviewFinding(
                    category="architecture",
                    severity="high",
                    title="Authentication requirements are not architecturally covered",
                    evidence=(
                        "RequirementAnalysis contains an affirmative authentication "
                        "requirement, but SystemArchitecture selects an explicit no-authentication value."
                    ),
                    recommendation=(
                        "Provide an authentication approach that addresses the "
                        "authoritative authentication-related requirements."
                    ),
                ),
                "Authentication-related requirements are not represented by the selected authentication approach.",
                "Authentication requirements are not architecturally covered.",
                "Update the authentication architecture to satisfy the explicit authentication requirements.",
            )

        if not required and not prohibited and selected_positive:
            assumptions = " ".join(
                architecture.architectural_assumptions
            ).casefold()
            labeled = any(
                term in assumptions
                for term in (
                    "authentication",
                    "login",
                    "sign in",
                    "credentials",
                    "authorization",
                    "access control",
                )
            )
            if not labeled:
                cls._add_finding(
                    report,
                    ReviewFinding(
                        category="assumption",
                        severity="medium",
                        title="Authentication introduced without explicit requirement support",
                        evidence=(
                            f"SystemArchitecture selects '{architecture.authentication}', "
                            "but RequirementAnalysis has no affirmative authentication "
                            "requirement and the choice is not labeled as an architectural assumption."
                        ),
                        recommendation=(
                            "Either obtain explicit authentication requirements or "
                            "record the authentication choice as an architectural assumption."
                        ),
                    ),
                    "Authentication was introduced without explicit authentication-related requirements.",
                    "Authentication was introduced without explicit requirement support.",
                    "Clarify whether authentication is required or label the selected approach as an assumption.",
                )

    @classmethod
    def _check_authentication_provenance(
        cls,
        report: ReviewReport,
        architecture: SystemArchitecture,
        registry: RequirementRegistry,
    ) -> None:
        auth_terms = (
            "authentication", "authenticate", "login", "log in", "sign in", "signin",
            "authorization", "authorisation", "password", "credentials", "access control",
            "jwt", "oauth",
        )
        explicit_claims = (
            "explicitly stated", "explicitly required", "requirements require",
            "requirements explicitly", "requirement requires", "required by the requirements",
            "required by requirements", "user requested", "user explicitly requested",
            "mandated by the requirements", "specified by the requirements",
        )
        negative_claims = (
            "no authentication required", "authentication not required",
            "authentication is not required", "no need for authentication",
            "authentication is unnecessary",
        )
        support_terms = auth_terms + ("account", "identity", "protected data")

        for decision in architecture.architecture_decisions:
            text = f"{decision.decision} {decision.rationale}".casefold()
            if not any(t in text for t in auth_terms):
                continue
            referenced = " ".join(
                registry.text_for_id(r).casefold()
                for r in decision.related_requirements
            )
            supported = any(t in referenced for t in support_terms)
            explicit = any(p in text for p in explicit_claims)
            negative = any(p in text for p in negative_claims)
            if not supported and (explicit or negative):
                cls._add_finding(
                    report,
                    ReviewFinding(
                        category="assumption",
                        severity="medium",
                        title="Architecture decision makes an unsupported authentication provenance claim",
                        evidence=f"Decision '{decision.decision}' references {decision.related_requirements}, but those authoritative requirements do not establish authentication. The decision/rationale presents authentication as explicitly supported or explicitly ruled out.",
                        recommendation="Rewrite the rationale as a technical choice or architectural assumption, or add an explicit authentication requirement if that is intended.",
                    ),
                    "An architecture decision incorrectly presents authentication as explicitly required or explicitly unrequired by the current requirements.",
                    "Authentication provenance was misrepresented in an architecture decision rationale.",
                    "Correct the authentication decision rationale so requirement absence is not represented as an explicit negative or positive requirement claim.",
                )

    @staticmethod
    def _architecture_fields(architecture: SystemArchitecture) -> list[tuple[str, str]]:
        fields: list[tuple[str, str]] = [
            ("architecture_style", architecture.architecture_style),
            ("frontend", architecture.frontend),
            ("backend", architecture.backend),
            ("database", architecture.database),
            ("authentication", architecture.authentication),
        ]
        fields.extend((f"data_flow[{i}]", value) for i, value in enumerate(architecture.data_flow))
        fields.extend((f"external_integrations[{i}]", value) for i, value in enumerate(architecture.external_integrations))
        fields.extend((f"architectural_assumptions[{i}]", value) for i, value in enumerate(architecture.architectural_assumptions))
        fields.extend((f"components[{i}].name", item.name) for i, item in enumerate(architecture.components))
        fields.extend((f"components[{i}].responsibility", item.responsibility) for i, item in enumerate(architecture.components))
        fields.extend((f"api_endpoints[{i}].name", item.name) for i, item in enumerate(architecture.api_endpoints))
        fields.extend((f"api_endpoints[{i}].purpose", item.purpose) for i, item in enumerate(architecture.api_endpoints))
        fields.extend((f"architecture_decisions[{i}].decision", item.decision) for i, item in enumerate(architecture.architecture_decisions))
        fields.extend((f"architecture_decisions[{i}].rationale", item.rationale) for i, item in enumerate(architecture.architecture_decisions))
        return fields

    @staticmethod
    def _is_negated_capability_mention(text: str, term: str, start: int, end: int) -> bool:
        before_words = re.findall(r"[\w'-]+", text[:start].casefold())[-6:]
        after_words = re.findall(r"[\w'-]+", text[end:].casefold())[:6]
        markers = {
            "no", "not", "never", "without", "avoid", "avoids", "avoided",
            "exclude", "excluded", "excluding", "omit", "omitted", "unsupported",
            "unrequested", "unneeded", "unnecessary", "outside", "isn't", "aren't",
            "wasn't", "weren't", "doesn't", "don't", "didn't", "cannot", "can't",
            "won't", "shouldn't", "mustn't",
        }
        before_negative = any(word in markers for word in before_words)
        after_negative = any(word in markers for word in after_words)
        if len(before_words) >= 2 and before_words[-2:] == ["not", "only"]:
            before_negative = False
        nearby = " ".join(before_words + [term.casefold()] + after_words)
        phrases = (
            "out of scope", "not in scope", "not required", "not needed",
            "not included", "not implemented", "not supported", "not requested",
            "not necessary", "not a requirement", "not part of the scope",
            "will not be", "will not include", "will not implement",
            "should not be", "must not be", "does not include", "does not support",
            "do not include", "do not support", "is not enabled", "is not provided",
            "are not enabled",
        )
        return before_negative or after_negative or any(p in nearby for p in phrases)

    @classmethod
    def _positive_term_matches(
        cls,
        architecture: SystemArchitecture,
        terms: tuple[str, ...],
    ) -> list[str]:
        findings: list[str] = []
        for field_name, value in cls._architecture_fields(architecture):
            text = value.casefold()
            for term in terms:
                for match in re.finditer(re.escape(term), text):
                    if cls._is_negated_capability_mention(text, term, match.start(), match.end()):
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
                    findings.append(f"{field_name} contains '{term}' in '{excerpt}'")
                    break
        return findings

    @classmethod
    def _has_positive_term(cls, text: str, terms: tuple[str, ...]) -> bool:
        normalized = text.casefold()
        for term in terms:
            for match in re.finditer(re.escape(term), normalized):
                if not cls._is_negated_capability_mention(
                    normalized, term, match.start(), match.end()
                ):
                    return True
        return False

    @classmethod
    def _check_realtime(
        cls,
        report: ReviewReport,
        requirement_text: str,
        architecture: SystemArchitecture,
    ) -> None:
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

        found = cls._positive_term_matches(architecture, tuple(terms_to_check))
        if found:
            cls._add_finding(
                report,
                ReviewFinding(
                    category="architecture",
                    severity="high",
                    title="Unsupported real-time or advanced tracking behavior",
                    evidence=(
                        "SystemArchitecture contains positive unsupported capability claims: "
                        + "; ".join(found)
                    ),
                    recommendation=(
                        "Remove these capabilities unless the authoritative requirements explicitly support them."
                    ),
                ),
                "Architecture introduces unsupported tracking, update, or notification behavior.",
                "Unsupported tracking, update, or notification behavior was introduced.",
                "Remove unsupported behavior or add explicit requirement support.",
            )

    @staticmethod
    def _is_speculative_tracking_assumption(
        text: str,
        start: int,
        end: int,
    ) -> bool:
        prefix = text[max(0, start - 100):start].casefold()
        clause = re.split(r"[.;\n]", prefix)[-1]
        return bool(
            re.search(
                r"\b(?:may|might|could|possibly|potentially)\s+"
                r"(?:also\s+)?(?:require|need|involve|depend on)\b",
                clause,
            )
            or re.search(r"\b(?:may|might|could)\s+(?:be\s+)?needed\b", clause)
        )

    @classmethod
    def _check_speculative_tracking_assumptions(
        cls,
        report: ReviewReport,
        requirement_text: str,
        architecture: SystemArchitecture,
    ) -> None:
        """Surface modal advanced-feature assumptions without treating them as implemented features."""
        families = (
            ("real-time updates", ("real-time", "realtime", "live updates", "instant updates", "websocket", "web sockets")),
            ("GPS/location tracking", ("gps tracking", "live gps", "live location", "location tracking", "continuous location")),
            ("push notifications", ("push notification", "push notifications")),
        )
        unsupported: list[str] = []
        for family_name, terms in families:
            if cls._has_positive_term(requirement_text, terms):
                continue
            for index, assumption in enumerate(architecture.architectural_assumptions):
                text = assumption.casefold()
                for term in terms:
                    for match in re.finditer(re.escape(term), text):
                        if cls._is_speculative_tracking_assumption(
                            text, match.start(), match.end()
                        ) and not cls._is_negated_capability_mention(
                            text, term, match.start(), match.end()
                        ):
                            unsupported.append(f"architectural_assumptions[{index}]: {assumption}")
                            break
                    if unsupported and unsupported[-1].startswith(f"architectural_assumptions[{index}]"):
                        break
        if unsupported:
            cls._add_finding(
                report,
                ReviewFinding(
                    category="assumption",
                    severity="low",
                    title="Advanced tracking capability is only a speculative assumption",
                    evidence=(
                        "The architecture lists advanced tracking/update behavior as a possibility, "
                        "not as an authorized requirement or selected design: "
                        + "; ".join(unsupported)
                    ),
                    recommendation=(
                        "Keep the delivered design limited to the requested status-tracking behavior. "
                        "Confirm the need explicitly before planning real-time updates, GPS/location tracking, "
                        "or push notifications."
                    ),
                ),
                action=(
                    "Confirm whether any advanced tracking/update capability is required; otherwise keep it out of scope."
                ),
            )

    @classmethod
    def _check_unresolved_integration_assumptions(
        cls,
        report: ReviewReport,
        architecture: SystemArchitecture,
    ) -> None:
        if architecture.external_integrations:
            return
        candidates = [
            assumption.strip()
            for assumption in architecture.architectural_assumptions
            if any(
                term in assumption.casefold()
                for term in (
                    "external payment service", "payment provider", "payment gateway",
                    "external service", "delivery provider", "third-party provider",
                )
            )
        ]
        if not candidates:
            return
        cls._add_finding(
            report,
            ReviewFinding(
                category="assumption",
                severity="low",
                title="Potential external integration boundaries need confirmation",
                evidence=(
                    "Architectural assumptions mention possible external dependencies, "
                    "but external_integrations is empty: " + "; ".join(candidates)
                ),
                recommendation=(
                    "Before implementation, confirm whether these provider dependencies are required. "
                    "Add only confirmed integrations to external_integrations and leave vendor selection open until decided."
                ),
            ),
            action=(
                "Confirm the payment-processing and delivery-status integration boundaries before implementation."
            ),
        )

    @classmethod
    def _check_discovery_enrichment(
        cls,
        report: ReviewReport,
        requirement_text: str,
        architecture: SystemArchitecture,
    ) -> None:
        if not any(
            term in requirement_text
            for term in ("discover restaurants", "restaurant discovery", "browse restaurants")
        ):
            return
        found = cls._positive_term_matches(
            architecture,
            (
                "user location", "location-based", "location based", "gps",
                "user preferences", "preferences", "personalization", "personalisation",
                "recommendation", "recommended restaurants",
            ),
        )
        if found:
            cls._add_finding(
                report,
                ReviewFinding(
                    category="architecture",
                    severity="medium",
                    title="Unsupported restaurant-discovery behavior",
                    evidence=(
                        "SystemArchitecture introduces restaurant-discovery behavior not established by RequirementAnalysis: "
                        + "; ".join(found)
                    ),
                    recommendation=(
                        "Keep restaurant discovery at the level specified by the requirements unless the additional behavior is explicitly confirmed."
                    ),
                ),
                "Architecture introduces unsupported restaurant-discovery behavior.",
                "Unsupported restaurant-discovery behavior was introduced.",
                "Remove unsupported restaurant-discovery behavior or clarify the requirement.",
            )

    @classmethod
    def _check_api_coverage(cls, report: ReviewReport, architecture: SystemArchitecture, registry: RequirementRegistry) -> None:
        if not architecture.api_endpoints:
            return
        api_ids = {
            ref
            for endpoint in architecture.api_endpoints
            for ref in registry.normalize_references(endpoint.related_requirements)
        }
        missing = [r for r in registry.ids if r not in api_ids]
        if missing:
            cls._add_finding(
                report,
                ReviewFinding(
                    category="traceability",
                    severity="high",
                    title="Functional requirements missing API coverage",
                    evidence="The following functional requirements are not represented by an API capability: " + ", ".join(missing),
                    recommendation="Add requirement-derived API capabilities or document why backend interaction is not needed.",
                ),
                "One or more functional requirements lack API coverage.",
                None,
                "Add API capabilities for the uncovered functional requirements or justify their absence.",
            )

    @staticmethod
    def _add_finding(
        report: ReviewReport,
        finding: ReviewFinding,
        consistency_issue: str | None = None,
        unsupported_addition: str | None = None,
        action: str | None = None,
    ) -> None:
        titles = {f.title.strip().casefold() for f in report.findings}
        if finding.title.strip().casefold() not in titles:
            report.findings.append(finding)
        if consistency_issue and consistency_issue not in report.architecture_consistency_issues:
            report.architecture_consistency_issues.append(consistency_issue)
        if unsupported_addition and unsupported_addition not in report.unsupported_additions:
            report.unsupported_additions.append(unsupported_addition)
        if action and action not in report.recommended_actions:
            report.recommended_actions.append(action)
        if finding.severity in {"medium", "high", "critical"}:
            report.overall_status = "NEEDS_REVISION"

    @staticmethod
    def _check_status(report: ReviewReport) -> None:
        material = any(f.severity in {"medium", "high", "critical"} for f in report.findings)
        has_material_issues = material or bool(report.unsupported_additions or report.architecture_consistency_issues)
        if report.overall_status == "PASS" and has_material_issues:
            raise ValueError("Review cannot be PASS when material findings or architecture issues are present.")
        if report.overall_status == "NEEDS_REVISION" and not has_material_issues:
            raise ValueError("Review is marked NEEDS_REVISION but no material review problem was identified.")

    @staticmethod
    def _check_problem_consistency(report: ReviewReport) -> None:
        if (report.unsupported_additions or report.architecture_consistency_issues) and not report.findings:
            raise ValueError("Review reported unsupported additions or architecture issues but findings is empty.")

    @staticmethod
    def _synchronize_recommended_actions(report: ReviewReport) -> None:
        """Every finding recommendation must be visible in the action list."""
        existing = {action.strip().casefold() for action in report.recommended_actions}
        for finding in report.findings:
            recommendation = finding.recommendation.strip()
            if recommendation and recommendation.casefold() not in existing:
                report.recommended_actions.append(recommendation)
                existing.add(recommendation.casefold())

    @staticmethod
    def _synchronize_summary(report: ReviewReport) -> None:
        if report.overall_status == "PASS":
            low_findings = [finding for finding in report.findings if finding.severity == "low"]
            if low_findings:
                report.summary = (
                    "Functional requirements are covered. Low-priority assumptions or integration "
                    "decisions remain to be confirmed; see findings and recommended actions."
                )
            return
        misleading = ("no unsupported additions", "no unsupported addition", "no critical inconsistencies", "no critical inconsistency", "no issues found", "no issues were found")
        if not report.summary.strip() or any(p in report.summary.casefold() for p in misleading):
            report.summary = "Review identified material issues that require revision; see findings and recommended actions."
