from app.core.execution.runner import AgentRunner
from app.core.llm.client import LocalLLMClient
from app.core.model_config import PROJECT_PLANNER_MODEL
from app.core.traceability.requirements import RequirementRegistry

from app.agents.requirement_analyst.schemas import RequirementAnalysis

from .prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .quality import ProjectPlanQualityController
from .schemas import ProjectPlan


MODEL_NAME = PROJECT_PLANNER_MODEL


class ProjectPlanner:
    """
    Project Planner Agent.

    Converts a validated RequirementAnalysis artifact
    into a validated, requirement-traceable ProjectPlan.
    """

    def __init__(
        self,
        model_name: str = MODEL_NAME,
        max_attempts: int = 2,
    ):
        self.llm_client = LocalLLMClient(
            model_name=model_name,
        )

        self.quality_controller = (
            ProjectPlanQualityController()
        )

        self.runner = AgentRunner(
            max_attempts=max_attempts
        )

    def plan(
        self,
        requirements: RequirementAnalysis,
    ) -> ProjectPlan:

        if not isinstance(
            requirements,
            RequirementAnalysis,
        ):
            raise TypeError(
                "Planner requires a RequirementAnalysis object."
            )

        registry = RequirementRegistry.from_analysis(
            requirements
        )

        context = {
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

        base_user_prompt = USER_PROMPT_TEMPLATE.format(
            context=context
        )

        def execute(
            previous_error: str | None,
        ) -> ProjectPlan:

            user_prompt = base_user_prompt

            if previous_error:
                user_prompt += f"""

PREVIOUS VALIDATION FEEDBACK
----------------------------
The previous ProjectPlan was rejected by the quality controller.

Validation error:
{previous_error}

Regenerate the COMPLETE ProjectPlan.

Fix the validation problem directly.

Remember:
- Every milestone must contain at least one requirement_refs entry.
- Every task must contain at least one requirement_refs entry.
- Every requirement reference must use canonical IDs such as FR-001.
- Every task reference must belong to its parent milestone references.
- Every functional requirement must be covered by at least one milestone.
- Do not invent new functional requirements.
- Keep tasks implementation-agnostic.
- Do not introduce APIs, technologies, or advanced features as requirements.

Return only the corrected ProjectPlan JSON.
"""

            plan = self.llm_client.generate_structured(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                output_schema=ProjectPlan,
            )

            return self.quality_controller.validate(
                plan,
                requirements,
                registry,
            )

        return self.runner.run(
            execute
        )