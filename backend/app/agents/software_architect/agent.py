from app.core.execution.runner import AgentRunner
from app.core.llm.client import LocalLLMClient

from app.agents.project_planner.schemas import ProjectPlan
from app.agents.requirement_analyst.schemas import RequirementAnalysis

from .prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .quality import ArchitectureQualityController
from .schemas import SystemArchitecture


MODEL_NAME = "qwen3:4b"


class SoftwareArchitect:
    """
    Software Architect Agent.

    Converts validated requirements and a project plan
    into a validated system architecture.
    """

    def __init__(
        self,
        model_name: str = MODEL_NAME,
        max_attempts: int = 2,
    ):
        # Architecture generation does not need unlimited output.
        # Keeping the generation bounded is important for CPU inference.
        self.llm_client = LocalLLMClient(
            model_name=model_name,
            num_predict=2400,
            keep_alive="30m",
        )

        self.quality_controller = ArchitectureQualityController()

        self.runner = AgentRunner(
            max_attempts=max_attempts
        )

    def design(
        self,
        requirements: RequirementAnalysis,
        project_plan: ProjectPlan,
    ) -> SystemArchitecture:

        if not isinstance(
            requirements,
            RequirementAnalysis,
        ):
            raise TypeError(
                "Architect requires a RequirementAnalysis object."
            )

        if not isinstance(
            project_plan,
            ProjectPlan,
        ):
            raise TypeError(
                "Architect requires a ProjectPlan object."
            )

        # Compact JSON reduces unnecessary prompt tokens compared
        # with model_dump_json(indent=2).
        requirements_json = requirements.model_dump_json()
        project_plan_json = project_plan.model_dump_json()

        # Build the base prompt only once.
        base_user_prompt = USER_PROMPT_TEMPLATE.format(
            requirements=requirements_json,
            project_plan=project_plan_json,
        )

        # Explicitly discourage verbose generation.
        base_user_prompt += """

ARCHITECTURE OUTPUT EFFICIENCY RULES:
- Return only the information required by the SystemArchitecture schema.
- Keep descriptions concise and technically specific.
- Do not add explanations, commentary, or prose outside the schema.
- Do not repeat the same information across multiple fields.
- Keep lists focused on the requirements and plan.
- Do not invent requirements, features, integrations, or behavior.
"""

        def execute(
            previous_error: str | None,
        ) -> SystemArchitecture:

            user_prompt = base_user_prompt

            if previous_error:
                user_prompt += f"""

The previous architecture was rejected.

Validation feedback:
{previous_error}

Regenerate the COMPLETE SystemArchitecture.

Make sure:
- Every component references a valid functional requirement.
- Every API capability references a valid functional requirement.
- data_flow is not empty.
- architecture_decisions is not empty.
- If the architecture mentions an external service, add it to external_integrations.
- Do not invent user requirements.
- Do not invent real-time behavior.
- Keep architecture_style consistent with the actual architecture.
- Keep the regenerated architecture concise.
"""

            architecture = self.llm_client.generate_structured(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                output_schema=SystemArchitecture,
            )

            return self.quality_controller.validate(
                architecture,
                requirements,
                project_plan,
            )

        return self.runner.run(execute)