from app.core.execution.runner import AgentRunner
from app.core.llm.client import LocalLLMClient
from app.core.traceability.requirements import RequirementRegistry

from app.agents.project_planner.schemas import ProjectPlan
from app.agents.requirement_analyst.schemas import RequirementAnalysis

from .prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .quality import ArchitectureQualityController
from .schemas import SystemArchitecture


MODEL_NAME = "qwen3:4b"


class SoftwareArchitect:
    def __init__(
        self,
        model_name: str = MODEL_NAME,
        max_attempts: int = 2,
    ):
        self.llm_client = LocalLLMClient(
            model_name=model_name,
            num_predict=2400,
            keep_alive="30m",
        )

        self.quality_controller = ArchitectureQualityController()
        self.runner = AgentRunner(max_attempts=max_attempts)

    def design(
        self,
        requirements: RequirementAnalysis,
        project_plan: ProjectPlan,
    ) -> SystemArchitecture:

        if not isinstance(requirements, RequirementAnalysis):
            raise TypeError(
                "requirements must be an instance of RequirementAnalysis."
            )

        if not isinstance(project_plan, ProjectPlan):
            raise TypeError(
                "project_plan must be an instance of ProjectPlan."
            )

        registry = RequirementRegistry.from_analysis(requirements)

        requirement_context = {
            "project_name": requirements.project_name,
            "objective": requirements.objective,
            "user_roles": requirements.user_roles,
            "functional_requirements": registry.to_prompt_text(),
            "non_functional_requirements": requirements.non_functional_requirements,
            "constraints": requirements.constraints,
            "assumptions": requirements.assumptions,
        }

        plan_context = {
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
        }

        base_user_prompt = USER_PROMPT_TEMPLATE.format(
            requirements=requirement_context,
            project_plan=plan_context,
        )

        def execute(previous_error: str | None):
            user_prompt = base_user_prompt

            if previous_error:
                user_prompt += f"""

PREVIOUS VALIDATION FEEDBACK
----------------------------
The previous architecture failed validation.

Validation error:
{previous_error}

Regenerate the complete architecture.

Fix the validation problem directly.

Do not remove required traceability.
Do not introduce new unsupported capabilities.
Return only the corrected SystemArchitecture JSON.
"""

            architecture = self.llm_client.generate_structured(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                output_schema=SystemArchitecture,
            )

            return self.quality_controller.validate(
                architecture=architecture,
                requirements=requirements,
                project_plan=project_plan,
                registry=registry,
            )

        return self.runner.run(execute)