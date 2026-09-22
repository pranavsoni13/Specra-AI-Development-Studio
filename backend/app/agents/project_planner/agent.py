from app.core.execution.runner import AgentRunner
from app.core.llm.client import LocalLLMClient
from app.core.traceability.requirements import RequirementRegistry

from app.agents.requirement_analyst.schemas import RequirementAnalysis

from .prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .quality import ProjectPlanQualityController
from .schemas import ProjectPlan


MODEL_NAME = "qwen3:4b"


class ProjectPlanner:
    """
    Project Planner Agent.

    Converts a validated RequirementAnalysis artifact into a validated
    ProjectPlan using canonical requirement IDs for traceability.
    """

    def __init__(
        self,
        model_name: str = MODEL_NAME,
        max_attempts: int = 2,
    ):
        self.llm_client = LocalLLMClient(
            model_name=model_name
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

        planner_context = self._build_planner_context(
            requirements,
            registry,
        )

        def execute(
            previous_error: str | None,
        ) -> ProjectPlan:

            user_prompt = USER_PROMPT_TEMPLATE.format(
                context=planner_context
            )

            if previous_error:
                user_prompt += f"""

The previous ProjectPlan was rejected by deterministic validation.

Validation feedback:
{previous_error}

Regenerate the COMPLETE ProjectPlan.

Correct only the reported validation problems.

Remember:
- Use canonical requirement IDs only.
- Every milestone needs requirement_refs.
- Every task needs requirement_refs.
- Every task reference must belong to its parent milestone.
- Every functional requirement must be covered.
- Do not invent product capabilities.
- Do not add implementation details that are absent from the requirements.
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

    @staticmethod
    def _build_planner_context(
        requirements: RequirementAnalysis,
        registry: RequirementRegistry,
    ) -> str:

        sections = [
            (
                "PROJECT NAME\n"
                f"{requirements.project_name}"
            ),
            (
                "OBJECTIVE\n"
                f"{requirements.objective}"
            ),
            (
                "USER ROLES\n"
                + (
                    "\n".join(
                        f"- {role}"
                        for role in requirements.user_roles
                    )
                    if requirements.user_roles
                    else "None explicitly identified."
                )
            ),
            registry.to_prompt_text(),
            (
                "NON-FUNCTIONAL REQUIREMENTS\n"
                + (
                    "\n".join(
                        f"- {item}"
                        for item in requirements.non_functional_requirements
                    )
                    if requirements.non_functional_requirements
                    else "None explicitly stated."
                )
            ),
            (
                "CONSTRAINTS\n"
                + (
                    "\n".join(
                        f"- {item}"
                        for item in requirements.constraints
                    )
                    if requirements.constraints
                    else "None explicitly stated."
                )
            ),
        ]

        return "\n\n".join(
            sections
        )