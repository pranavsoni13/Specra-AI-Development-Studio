from app.core.execution.runner import AgentRunner
from app.core.llm.client import LocalLLMClient

from app.agents.requirement_analyst.schemas import RequirementAnalysis

from .prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .quality import ProjectPlanQualityController
from .schemas import ProjectPlan


MODEL_NAME = "qwen3:4b"


class ProjectPlanner:
    """
    Project Planner Agent.

    Converts a validated RequirementAnalysis artifact
    into a validated ProjectPlan using the shared
    LLM and execution infrastructure.
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

        requirements_json = (
            requirements.model_dump_json(
                indent=2
            )
        )

        def execute(
            previous_error: str | None,
        ) -> ProjectPlan:

            user_prompt = USER_PROMPT_TEMPLATE.format(
                requirements=requirements_json
            )

            if previous_error:
                user_prompt += f"""

The previous ProjectPlan was rejected by the
quality controller.

Validation feedback:
{previous_error}

Regenerate the ProjectPlan and correct the problem.

Remember:
- Every milestone must contain at least one requirement_refs entry.
- Every requirement reference must exactly match a
  functional requirement.
- Every milestone must contain at least one task.
- The plan must contain meaningful milestones.
"""

            plan = self.llm_client.generate_structured(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                output_schema=ProjectPlan,
            )

            return self.quality_controller.validate(
                plan,
                requirements,
            )

        return self.runner.run(execute)