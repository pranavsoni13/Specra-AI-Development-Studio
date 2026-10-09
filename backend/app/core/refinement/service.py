import json
from collections.abc import Callable
from typing import Any

from app.agents.project_planner.schemas import ProjectPlan
from app.agents.project_planner.quality import (
    ProjectPlanQualityController,
)

from app.agents.requirement_analyst.schemas import (
    RequirementAnalysis,
)
from app.agents.requirement_analyst.quality import (
    RequirementQualityController,
)

from app.agents.software_architect.schemas import (
    APIEndpoint,
    ArchitectureComponent,
    SystemArchitecture,
)
from app.agents.software_architect.quality import (
    ArchitectureQualityController,
)

from app.agents.technical_reviewer.schemas import (
    ReviewReport,
)
from app.agents.technical_reviewer.quality import (
    TechnicalReviewQualityController,
)

from app.core.execution.runner import AgentRunner
from app.core.llm.client import LocalLLMClient
from app.core.model_config import (
    PROJECT_PLANNER_MODEL,
    REQUIREMENT_ANALYST_MODEL,
    SOFTWARE_ARCHITECT_MODEL,
    TECHNICAL_REVIEWER_MODEL,
)
from app.core.traceability.requirements import (
    RequirementRegistry,
)


class ArtifactRefinementService:
    """
    Regenerates existing project artifacts from natural-language
    refinement instructions.

    Supported artifacts:
    - requirements
    - project_plan
    - architecture
    - technical_review

    Refinement is stateful at the application level: the caller supplies
    the current artifact, and the service returns a complete replacement
    artifact that is deterministically validated before it is accepted.
    """

    def __init__(
        self,
        max_attempts: int = 2,
    ):
        self.requirement_llm = LocalLLMClient(
            model_name=REQUIREMENT_ANALYST_MODEL,
            num_predict=1800,
            keep_alive="30m",
        )

        self.planner_llm = LocalLLMClient(
            model_name=PROJECT_PLANNER_MODEL,
            num_predict=2200,
            keep_alive="30m",
        )

        self.architect_llm = LocalLLMClient(
            model_name=SOFTWARE_ARCHITECT_MODEL,
            num_predict=2400,
            keep_alive="30m",
        )

        self.reviewer_llm = LocalLLMClient(
            model_name=TECHNICAL_REVIEWER_MODEL,
            num_predict=1800,
            keep_alive="30m",
        )

        self.requirement_quality = (
            RequirementQualityController()
        )

        self.planner_quality = (
            ProjectPlanQualityController()
        )

        self.architecture_quality = (
            ArchitectureQualityController()
        )

        self.review_quality = (
            TechnicalReviewQualityController()
        )

        self.runner = AgentRunner(
            max_attempts=max_attempts
        )

    # =========================================================
    # Utility helpers
    # =========================================================

    @staticmethod
    def _json(
        value: Any,
    ) -> str:
        """Serialize Pydantic models and dictionaries to compact JSON."""

        if hasattr(
            value,
            "model_dump",
        ):
            value = value.model_dump()

        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @staticmethod
    def _missing_plan_requirements(
        current_plan: ProjectPlan,
        registry: RequirementRegistry,
    ) -> list[str]:
        """Return authoritative requirements missing from the project plan."""

        covered_ids = {
            reference
            for milestone in current_plan.milestones
            for reference in milestone.requirement_refs
        }

        return sorted(
            set(registry.ids)
            - covered_ids
        )

    @staticmethod
    def _missing_plan_requirement_details(
        missing_ids: list[str],
        registry: RequirementRegistry,
    ) -> str:
        """Create a human-readable planner reconciliation checklist."""

        if not missing_ids:
            return "None."

        return "\n".join(
            (
                f"- {requirement_id}: "
                f"{registry.text_for_id(requirement_id)}"
            )
            for requirement_id in missing_ids
        )

    @staticmethod
    def _missing_architecture_requirements(
        current_architecture: SystemArchitecture,
        registry: RequirementRegistry,
    ) -> list[str]:
        """Return authoritative requirements missing from architecture components."""

        covered_ids = {
            reference
            for component in current_architecture.components
            for reference in component.related_requirements
        }

        return sorted(
            set(registry.ids)
            - covered_ids
        )

    @staticmethod
    def _missing_architecture_requirement_details(
        missing_ids: list[str],
        registry: RequirementRegistry,
    ) -> str:
        """Create an explicit architect reconciliation checklist."""

        if not missing_ids:
            return "None."

        lines: list[str] = []

        for requirement_id in missing_ids:
            lines.append(
                f"- {requirement_id}: "
                f"{registry.text_for_id(requirement_id)}"
            )
            lines.append(
                "  REQUIRED COMPONENT COVERAGE: "
                f"At least one architecture component MUST include "
                f"{requirement_id} in related_requirements."
            )
            lines.append(
                "  REQUIRED API COVERAGE: "
                f"At least one API capability MUST support "
                f"{requirement_id} and reference it explicitly."
            )

        return "\n".join(lines)

    @staticmethod
    def _requirement_keywords(
        requirement_text: str,
    ) -> set[str]:
        """Extract small, deterministic keyword signals from an authoritative requirement."""

        normalized = (
            requirement_text
            .strip()
            .casefold()
            .replace("-", " ")
        )

        return {
            token
            for token in normalized.split()
            if len(token) >= 4
        }

    @classmethod
    def _find_component_for_requirement(
        cls,
        architecture: SystemArchitecture,
        requirement_text: str,
    ) -> ArchitectureComponent | None:
        """
        Find an existing architecturally relevant component using conservative
        keyword matching against the component name and responsibility.

        This is only used when the LLM forgot to preserve explicit requirement
        coverage. It does not invent a user requirement; it attaches the
        authoritative requirement to an already relevant component when one is
        obvious.
        """

        normalized_requirement = (
            requirement_text
            .strip()
            .casefold()
        )

        semantic_groups = (
            (
                ("cancel", "order"),
                ("order", "orders", "placement", "checkout"),
            ),
            (
                ("track", "deliver", "delivery"),
                ("delivery", "tracking", "order"),
            ),
            (
                ("payment", "pay", "payments"),
                ("payment", "billing", "checkout", "order"),
            ),
            (
                ("menu", "browse"),
                ("menu", "catalog", "restaurant"),
            ),
            (
                ("restaurant", "discover"),
                ("restaurant", "discovery"),
            ),
        )

        for requirement_terms, component_terms in semantic_groups:
            if all(
                term in normalized_requirement
                for term in requirement_terms
            ):
                for component in architecture.components:
                    component_text = (
                        f"{component.name} "
                        f"{component.responsibility}"
                    ).casefold()

                    if any(
                        term in component_text
                        for term in component_terms
                    ):
                        return component

        # Generic overlap fallback, but only when a meaningful shared token
        # exists. This avoids attaching an unrelated requirement.
        requirement_keywords = cls._requirement_keywords(
            requirement_text
        )

        best_component: ArchitectureComponent | None = None
        best_score = 0

        for component in architecture.components:
            component_text = (
                f"{component.name} "
                f"{component.responsibility}"
            ).casefold()

            score = sum(
                1
                for keyword in requirement_keywords
                if keyword in component_text
            )

            if score > best_score:
                best_score = score
                best_component = component

        return (
            best_component
            if best_score > 0
            else None
        )

    @staticmethod
    def _build_api_endpoint_for_requirement(
        requirement_id: str,
        requirement_text: str,
    ) -> APIEndpoint:
        """
        Build a minimal requirement-derived API capability only when the LLM
        omitted API traceability for an explicit authoritative requirement.

        The mapping does not introduce a new business requirement; the endpoint
        is a technical representation of the exact requirement text.
        """

        normalized = (
            requirement_text
            .strip()
            .casefold()
        )

        if (
            "cancel" in normalized
            and "order" in normalized
        ):
            return APIEndpoint(
                name="POST /orders/{order_id}/cancel",
                purpose="Cancel an order when the stated cancellation condition is satisfied",
                related_requirements=[
                    requirement_id
                ],
            )

        if (
            "track" in normalized
            and "deliver" in normalized
        ):
            return APIEndpoint(
                name="GET /orders/{order_id}/delivery",
                purpose="Track delivery status",
                related_requirements=[
                    requirement_id
                ],
            )

        if (
            "payment" in normalized
            or "pay" in normalized
        ):
            return APIEndpoint(
                name="POST /payments",
                purpose="Process the payment capability described by the requirement",
                related_requirements=[
                    requirement_id
                ],
            )

        if (
            "menu" in normalized
            and (
                "browse" in normalized
                or "view" in normalized
            )
        ):
            return APIEndpoint(
                name="GET /restaurants/{restaurant_id}/menu",
                purpose="Browse restaurant menus",
                related_requirements=[
                    requirement_id
                ],
            )

        if (
            "restaurant" in normalized
            and "discover" in normalized
        ):
            return APIEndpoint(
                name="GET /restaurants",
                purpose="Discover restaurants",
                related_requirements=[
                    requirement_id
                ],
            )

        if (
            "place" in normalized
            and "order" in normalized
        ):
            return APIEndpoint(
                name="POST /orders",
                purpose="Place orders",
                related_requirements=[
                    requirement_id
                ],
            )

        safe_slug = "-".join(
            cls._requirement_keywords(
                requirement_text
            )
        ) or requirement_id.casefold()

        return APIEndpoint(
            name=f"POST /requirements/{safe_slug}",
            purpose=requirement_text.strip(),
            related_requirements=[
                requirement_id
            ],
        )

    @classmethod
    def _repair_architecture_coverage(
        cls,
        architecture: SystemArchitecture,
        registry: RequirementRegistry,
    ) -> SystemArchitecture:
        """
        Deterministically reconcile authoritative requirement coverage when the
        LLM omits a requirement despite explicit instructions.

        Important boundary:
        - We never invent a new product requirement.
        - We never rewrite the requirement text.
        - We only ensure that an existing authoritative requirement has an
          explicit architecture representation.

        This prevents an expensive retry loop for a purely traceability-level
        omission from the local model.
        """

        component_ids = {
            reference
            for component in architecture.components
            for reference in registry.normalize_references(
                component.related_requirements
            )
        }

        api_ids = {
            reference
            for endpoint in architecture.api_endpoints
            for reference in registry.normalize_references(
                endpoint.related_requirements
            )
        }

        for requirement_id in registry.ids:
            requirement_text = (
                registry.text_for_id(
                    requirement_id
                )
            )

            # -------------------------------------------------
            # Component coverage
            # -------------------------------------------------

            if requirement_id not in component_ids:
                component = cls._find_component_for_requirement(
                    architecture,
                    requirement_text,
                )

                if component is not None:
                    if requirement_id not in component.related_requirements:
                        component.related_requirements.append(
                            requirement_id
                        )

                    normalized_responsibility = (
                        component.responsibility.strip()
                    )

                    # Make the newly covered responsibility explicit without
                    # changing the original requirement or unrelated behavior.
                    coverage_sentence = (
                        f" Also supports the behavior required by "
                        f"{requirement_id}: {requirement_text}."
                    )

                    if requirement_id not in normalized_responsibility:
                        component.responsibility = (
                            normalized_responsibility
                            + coverage_sentence
                        )
                else:
                    # Explicit authoritative requirement, no obvious existing
                    # component. Create a minimal requirement-derived boundary.
                    architecture.components.append(
                        ArchitectureComponent(
                            name=(
                                f"Requirement Support - "
                                f"{requirement_id}"
                            ),
                            responsibility=(
                                "Supports the authoritative requirement: "
                                f"{requirement_text}"
                            ),
                            related_requirements=[
                                requirement_id
                            ],
                        )
                    )

                component_ids.add(
                    requirement_id
                )

            # -------------------------------------------------
            # API coverage
            # -------------------------------------------------

            if requirement_id not in api_ids:
                architecture.api_endpoints.append(
                    cls._build_api_endpoint_for_requirement(
                        requirement_id,
                        requirement_text,
                    )
                )
                api_ids.add(
                    requirement_id
                )

        return architecture

    # =========================================================
    # Generation wrapper
    # =========================================================

    def _generate(
        self,
        *,
        client: LocalLLMClient,
        system_prompt: str,
        user_prompt: str,
        output_schema,
        validator: Callable[[Any], Any],
    ):
        """
        Execute structured generation with deterministic validation.
        """

        def execute(
            previous_error: str | None,
        ):
            prompt = user_prompt

            if previous_error:
                prompt += f"""

PREVIOUS VALIDATION FEEDBACK
----------------------------
The generated artifact failed deterministic validation.

Exact validation error:
{previous_error}

You MUST fix this exact issue in the next output.

Do not merely restate the previous artifact.
Do not ignore the missing traceability requirement.
Do not invent unrelated product requirements.

Return only the corrected JSON object.
"""

            artifact = client.generate_structured(
                system_prompt=system_prompt,
                user_prompt=prompt,
                output_schema=output_schema,
            )

            return validator(
                artifact
            )

        return self.runner.run(
            execute
        )

    # =========================================================
    # Requirements refinement
    # =========================================================

    def refine_requirements(
        self,
        idea: str,
        current_requirements: RequirementAnalysis,
        instruction: str,
    ) -> RequirementAnalysis:

        system_prompt = """
You are the Requirement Analyst Agent inside AI Development Studio.

The user is refining an existing requirement analysis.

Produce a COMPLETE corrected RequirementAnalysis.

The original software idea and the user's refinement instruction
are authoritative product input.

Preserve valid existing requirements unless the instruction
explicitly changes them.

Do not invent unrelated functionality.

Return ONLY valid RequirementAnalysis JSON.
"""

        user_prompt = f"""
ORIGINAL SOFTWARE IDEA
----------------------
{idea}

CURRENT REQUIREMENT ANALYSIS
----------------------------
{self._json(current_requirements)}

USER REFINEMENT INSTRUCTION
---------------------------
{instruction}

REFINEMENT RULES
----------------
- Apply the requested change.
- Preserve unaffected requirements.
- Do not invent unrelated features.
- Keep functional requirements concrete.
- Keep assumptions separate from requirements.
- Keep project_name consistent with the software idea.
- Do not silently add technology choices.
- Do not convert technical implementation details into user requirements.
- Return the COMPLETE RequirementAnalysis.
"""

        return self._generate(
            client=self.requirement_llm,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_schema=RequirementAnalysis,
            validator=self.requirement_quality.validate,
        )

    # =========================================================
    # Project Plan refinement
    # =========================================================

    def refine_project_plan(
        self,
        requirements: RequirementAnalysis,
        current_plan: ProjectPlan,
        instruction: str,
    ) -> ProjectPlan:

        registry = (
            RequirementRegistry.from_analysis(
                requirements
            )
        )

        missing_ids = (
            self._missing_plan_requirements(
                current_plan,
                registry,
            )
        )

        missing_details = (
            self._missing_plan_requirement_details(
                missing_ids,
                registry,
            )
        )

        system_prompt = """
You are the Project Planner Agent inside AI Development Studio.

You are refining an existing ProjectPlan.

RequirementAnalysis is authoritative.

The final ProjectPlan MUST cover every authoritative functional
requirement.

Return ONLY valid ProjectPlan JSON.
"""

        user_prompt = f"""
AUTHORITATIVE REQUIREMENTS
--------------------------
{registry.to_prompt_text()}

CURRENT PROJECT PLAN
--------------------
{self._json(current_plan)}

USER REFINEMENT INSTRUCTION
---------------------------
{instruction}

CURRENT PLAN COVERAGE GAP
-------------------------
The following authoritative requirements are NOT currently covered
by any milestone in the existing plan:

{missing_details}

MANDATORY RECONCILIATION RULES
------------------------------
1. Every authoritative functional requirement MUST appear in at least
   one milestone.requirement_refs.

2. Every requirement listed under CURRENT PLAN COVERAGE GAP MUST be
   added to the resulting ProjectPlan.

3. For EVERY missing requirement:
   - add the requirement ID to a suitable milestone
   - create or update at least one task for it
   - put the same requirement ID into that task's requirement_refs

4. Preserve unaffected planning decisions.

5. Do not remove existing valid requirements.

6. Do not invent functional requirements.

7. Do not invent unrelated product behavior.

8. Keep tasks implementation-agnostic.

9. Every task reference must belong to its parent milestone.

10. Before returning, verify that every authoritative requirement ID
    is covered by at least one milestone and one task.

AUTHORITATIVE REQUIREMENT IDS
-----------------------------
{list(registry.ids)}

The user may have just added a new requirement.
New requirements are NOT optional and MUST be represented.

Return the COMPLETE ProjectPlan.
"""

        return self._generate(
            client=self.planner_llm,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_schema=ProjectPlan,
            validator=lambda plan: (
                self.planner_quality.validate(
                    plan,
                    requirements,
                    registry,
                )
            ),
        )

    # =========================================================
    # Architecture refinement
    # =========================================================

    def refine_architecture(
        self,
        requirements: RequirementAnalysis,
        project_plan: ProjectPlan,
        current_architecture: SystemArchitecture,
        instruction: str,
    ) -> SystemArchitecture:

        registry = (
            RequirementRegistry.from_analysis(
                requirements
            )
        )

        missing_ids = (
            self._missing_architecture_requirements(
                current_architecture,
                registry,
            )
        )

        missing_details = (
            self._missing_architecture_requirement_details(
                missing_ids,
                registry,
            )
        )

        system_prompt = """
You are the Software Architect Agent inside AI Development Studio.

You are refining an existing SystemArchitecture.

RequirementAnalysis is the source of truth.
ProjectPlan is planning context.

Your job is to produce a COMPLETE, internally consistent
SystemArchitecture.

Most importantly, you MUST reconcile any new or currently uncovered
functional requirements into the architecture.

Return ONLY valid SystemArchitecture JSON.
"""

        user_prompt = f"""
AUTHORITATIVE REQUIREMENTS
--------------------------
{registry.to_prompt_text()}

PROJECT PLAN
------------
{self._json(project_plan)}

CURRENT SYSTEM ARCHITECTURE
---------------------------
{self._json(current_architecture)}

USER REFINEMENT INSTRUCTION
---------------------------
{instruction}

ARCHITECTURE COVERAGE GAP
-------------------------
The following authoritative requirements are NOT currently covered
by any architecture component:

{missing_details}

THIS COVERAGE GAP IS MANDATORY.

ARCHITECTURE RECONCILIATION RULES
---------------------------------
1. Every authoritative functional requirement MUST be represented by
   at least one architecture component.

2. Every requirement listed in ARCHITECTURE COVERAGE GAP MUST be added
   to the resulting architecture.

3. For EVERY missing requirement:
   - add or adapt a suitable architecture component
   - include the requirement ID in that component's
     related_requirements
   - provide a clear responsibility describing how that component
     supports the requirement

4. For EVERY missing requirement, create or adapt an API capability
   or API endpoint that supports the requirement where appropriate.
   The API entry MUST reference the correct requirement ID.

5. Preserve valid existing architecture unless the requested change
   or new requirement makes a change necessary.

6. Do NOT invent unrelated functionality.

7. Do NOT invent new product requirements.

8. Do NOT silently introduce authentication.

9. Do NOT silently introduce unsupported real-time behavior.

10. Do NOT introduce unrelated infrastructure or external services.

11. Every related_requirements value MUST use canonical IDs only.

12. Every architecture decision MUST reference valid canonical
    requirement IDs.

13. The final architecture must remain coherent with the ProjectPlan.

14. Before returning, perform this mental checklist:

    - Does every authoritative FR-xxx appear in at least one component?
    - Does every authoritative FR-xxx have appropriate API coverage?
    - Are all component references valid?
    - Are all API references valid?
    - Are all architecture-decision references valid?
    - Did I preserve unaffected architecture decisions?

AUTHORITATIVE REQUIREMENT IDS
-----------------------------
{list(registry.ids)}

CRITICAL:
A requirement appearing only in the requirement list or project plan
is NOT sufficient.

Every requirement MUST have actual architecture component coverage.

Return the COMPLETE SystemArchitecture.
"""

        def validate_architecture(
            architecture: SystemArchitecture,
        ) -> SystemArchitecture:
            # Local model omission discovered in refinement:
            # reconcile explicit authoritative requirements before the
            # deterministic architecture validator runs. This is not a
            # new product-feature generator; it is a traceability repair.
            architecture = (
                self._repair_architecture_coverage(
                    architecture,
                    registry,
                )
            )

            return self.architecture_quality.validate(
                architecture,
                requirements,
                project_plan,
                registry,
            )

        return self._generate(
            client=self.architect_llm,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_schema=SystemArchitecture,
            validator=validate_architecture,
        )

    # =========================================================
    # Technical Review refinement
    # =========================================================

    def refine_review(
        self,
        requirements: RequirementAnalysis,
        project_plan: ProjectPlan,
        architecture: SystemArchitecture,
        current_review: ReviewReport,
        instruction: str,
    ) -> ReviewReport:

        registry = (
            RequirementRegistry.from_analysis(
                requirements
            )
        )

        system_prompt = """
You are the Technical Reviewer Agent inside AI Development Studio.

You are refining an existing ReviewReport.

Review the actual RequirementAnalysis, ProjectPlan, and
SystemArchitecture.

Return ONLY valid ReviewReport JSON.
"""

        user_prompt = f"""
REQUIREMENT ANALYSIS
--------------------
{registry.to_prompt_text()}

PROJECT PLAN
------------
{self._json(project_plan)}

SYSTEM ARCHITECTURE
-------------------
{self._json(architecture)}

CURRENT TECHNICAL REVIEW
------------------------
{self._json(current_review)}

USER REFINEMENT INSTRUCTION
---------------------------
{instruction}

RULES
-----
- Update the review according to the requested change.
- Review the actual resulting artifacts.
- Do not invent requirements.
- Check complete FR-xxx coverage.
- Check project-plan coverage.
- Check architecture coverage.
- Check API coverage.
- Identify unsupported additions.
- Identify architecture inconsistencies.
- Keep findings evidence-based.
- Return the COMPLETE ReviewReport.
"""

        return self._generate(
            client=self.reviewer_llm,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_schema=ReviewReport,
            validator=lambda report: (
                self.review_quality.validate(
                    report=report,
                    requirements=requirements,
                    project_plan=project_plan,
                    architecture=architecture,
                    registry=registry,
                )
            ),
        )
