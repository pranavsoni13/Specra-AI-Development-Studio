import json

from app.core.execution.runner import AgentRunner
from app.core.llm.client import LocalLLMClient
from app.core.model_config import TECHNICAL_REVIEWER_MODEL
from app.core.traceability.requirements import RequirementRegistry

from app.agents.project_planner.schemas import ProjectPlan
from app.agents.requirement_analyst.schemas import RequirementAnalysis
from app.agents.software_architect.schemas import SystemArchitecture

from .prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .quality import TechnicalReviewQualityController
from .schemas import ReviewReport


MODEL_NAME = TECHNICAL_REVIEWER_MODEL


class TechnicalReviewer:
    """
    Technical Reviewer Agent.

    Independently audits the RequirementAnalysis, ProjectPlan,
    and SystemArchitecture artifacts.
    """

    def __init__(
        self,
        model_name: str = MODEL_NAME,
        max_attempts: int = 2,
    ):
        self.llm_client = LocalLLMClient(
            model_name=model_name,
            num_predict=1800,
            keep_alive="30m",
        )

        self.quality_controller = (
            TechnicalReviewQualityController()
        )

        self.runner = AgentRunner(
            max_attempts=max_attempts
        )

    def review(
        self,
        requirements: RequirementAnalysis,
        project_plan: ProjectPlan,
        architecture: SystemArchitecture,
    ) -> ReviewReport:

        if not isinstance(
            requirements,
            RequirementAnalysis,
        ):
            raise TypeError(
                "Reviewer requires a RequirementAnalysis object."
            )

        if not isinstance(
            project_plan,
            ProjectPlan,
        ):
            raise TypeError(
                "Reviewer requires a ProjectPlan object."
            )

        if not isinstance(
            architecture,
            SystemArchitecture,
        ):
            raise TypeError(
                "Reviewer requires a SystemArchitecture object."
            )

        registry = RequirementRegistry.from_analysis(
            requirements
        )

        requirement_context = {
            "project_name": requirements.project_name,
            "objective": requirements.objective,
            "user_roles": requirements.user_roles,
            "functional_requirements": registry.to_prompt_text(),
            "non_functional_requirements": (
                requirements.non_functional_requirements
            ),
            "constraints": requirements.constraints,
            "assumptions": requirements.assumptions,
        }

        project_plan_context = {
            "project_name": project_plan.project_name,
            "milestones": [
                {
                    "name": milestone.name,
                    "description": milestone.description,
                    "requirement_refs": milestone.requirement_refs,
                    "tasks": [
                        {
                            "description": task.description,
                            "requirement_refs": task.requirement_refs,
                        }
                        for task in milestone.tasks
                    ],
                }
                for milestone in project_plan.milestones
            ],
            "dependencies": project_plan.dependencies,
            "development_sequence": project_plan.development_sequence,
        }

        architecture_context = {
            "project_name": architecture.project_name,
            "architecture_style": architecture.architecture_style,
            "frontend": architecture.frontend,
            "backend": architecture.backend,
            "database": architecture.database,
            "authentication": architecture.authentication,
            "components": [
                {
                    "name": component.name,
                    "responsibility": component.responsibility,
                    "related_requirements": (
                        component.related_requirements
                    ),
                }
                for component in architecture.components
            ],
            "api_endpoints": [
                {
                    "name": endpoint.name,
                    "purpose": endpoint.purpose,
                    "related_requirements": (
                        endpoint.related_requirements
                    ),
                }
                for endpoint in architecture.api_endpoints
            ],
            "data_flow": architecture.data_flow,
            "external_integrations": (
                architecture.external_integrations
            ),
            "architectural_assumptions": (
                architecture.architectural_assumptions
            ),
            "architecture_decisions": [
                {
                    "decision": decision.decision,
                    "rationale": decision.rationale,
                    "related_requirements": (
                        decision.related_requirements
                    ),
                }
                for decision in architecture.architecture_decisions
            ],
        }

        base_user_prompt = USER_PROMPT_TEMPLATE.format(
            requirements=json.dumps(
                requirement_context,
                separators=(",", ":"),
            ),
            project_plan=json.dumps(
                project_plan_context,
                separators=(",", ":"),
            ),
            architecture=json.dumps(
                architecture_context,
                separators=(",", ":"),
            ),
        )

        def execute(
            previous_error: str | None,
        ) -> ReviewReport:

            user_prompt = base_user_prompt

            if previous_error:
                user_prompt += f"""

==================================================
PREVIOUS VALIDATION FEEDBACK
==================================================

The previous ReviewReport was rejected by the deterministic
quality controller.

Validation error:
{previous_error}

Regenerate the COMPLETE ReviewReport.

Fix the specific validation problem.

Do not invent new requirements.

Keep every coverage entry aligned with the canonical requirement IDs.

Return ONLY the corrected ReviewReport JSON.
"""

            report = self.llm_client.generate_structured(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                output_schema=ReviewReport,
            )

            return self.quality_controller.validate(
                report=report,
                requirements=requirements,
                project_plan=project_plan,
                architecture=architecture,
                registry=registry,
            )

        return self.runner.run(
            execute
        )