from app.core.execution.runner import AgentRunner
from app.core.llm.client import LocalLLMClient
from app.core.model_config import SOFTWARE_ARCHITECT_MODEL
from app.core.traceability.requirements import RequirementRegistry

from app.agents.project_planner.schemas import ProjectPlan
from app.agents.requirement_analyst.schemas import RequirementAnalysis

from .prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .quality import ArchitectureQualityController
from .schemas import SystemArchitecture


MODEL_NAME = SOFTWARE_ARCHITECT_MODEL


class SoftwareArchitect:
    """
    Software Architect Agent.

    Converts validated requirements and a validated project plan
    into a requirement-traceable system architecture.
    """

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

        registry = RequirementRegistry.from_analysis(
            requirements
        )

        requirement_text = " ".join(
            [
                requirements.objective,
                *requirements.functional_requirements,
                *requirements.non_functional_requirements,
                *requirements.constraints,
            ]
        ).casefold()

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
                "user accounts",
                "authorization",
                "authorisation",
            )
        )

        requirement_context = {
            "project_name": requirements.project_name,
            "objective": requirements.objective,
            "user_roles": requirements.user_roles,
            "functional_requirements": (
                registry.to_prompt_text()
            ),
            "non_functional_requirements": (
                requirements.non_functional_requirements
            ),
            "constraints": requirements.constraints,
            "assumptions": requirements.assumptions,
            "authentication_required": (
                "YES"
                if authentication_required
                else "NO"
            ),
        }

        plan_context = {
            "project_name": project_plan.project_name,
            "milestones": [
                {
                    "name": milestone.name,
                    "description": milestone.description,
                    "requirement_refs": (
                        milestone.requirement_refs
                    ),
                    "tasks": [
                        {
                            "description": task.description,
                            "requirement_refs": (
                                task.requirement_refs
                            ),
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

        base_user_prompt += """

ARCHITECTURE OUTPUT EFFICIENCY RULES:
- Return only information required by the SystemArchitecture schema.
- Keep descriptions concise and technically specific.
- Do not add explanations or commentary outside the schema.
- Do not repeat the same information across multiple fields.
- Keep lists focused on the requirements and project plan.
- Do not invent requirements, features, integrations, or behavior.
"""

        def execute(
            previous_error: str | None,
        ) -> SystemArchitecture:

            user_prompt = base_user_prompt

            if previous_error:
                user_prompt += f"""

PREVIOUS VALIDATION FEEDBACK
----------------------------
The previous architecture was rejected by the quality controller.

Validation error:
{previous_error}

Regenerate the COMPLETE SystemArchitecture.

Fix the validation problem directly.

IMPORTANT:
The validation feedback is authoritative for correcting the previous
architecture, but it does NOT create new product requirements.

Remember:
- Every component must reference valid requirement IDs.
- Every API endpoint must reference valid requirement IDs.
- Every architecture decision must reference valid requirement IDs.
- Every functional requirement must be covered by a component.
- Every functional requirement requiring backend behavior must be represented by an API capability.
- Do not introduce unsupported authentication.
- Do not introduce unsupported restaurant-discovery behavior.
- Do not introduce real-time behavior unless explicitly required.
- Keep architecture_style consistent with the architecture.
- Keep the regenerated architecture concise.
"""

            architecture = (
                self.llm_client.generate_structured(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    output_schema=SystemArchitecture,
                )
            )

            return self.quality_controller.validate(
                architecture,
                requirements,
                project_plan,
                registry,
            )

        return self.runner.run(
            execute
        )