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
    """
    Software Architect Agent.

    Converts validated requirements and a project plan into a traceable,
    validated system architecture.
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

        architecture_context = self._build_architecture_context(
            requirements,
            project_plan,
            registry,
        )

        def execute(
            previous_error: str | None,
        ) -> SystemArchitecture:

            user_prompt = USER_PROMPT_TEMPLATE.format(
                context=architecture_context
            )

            if previous_error:
                user_prompt += f"""

The previous SystemArchitecture was rejected by deterministic validation.

Validation feedback:
{previous_error}

Regenerate the COMPLETE SystemArchitecture.

Correct the reported validation problem while preserving traceability.

Remember:
- RequirementAnalysis is authoritative.
- Use canonical requirement IDs only.
- Every component needs related_requirements.
- Every API capability needs related_requirements.
- Every architecture decision needs related_requirements.
- Do not introduce unsupported product behavior.
- Keep the architecture concise.
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
                registry,
            )

        return self.runner.run(
            execute
        )

    @staticmethod
    def _build_architecture_context(
        requirements: RequirementAnalysis,
        project_plan: ProjectPlan,
        registry: RequirementRegistry,
    ) -> str:

        requirement_section = registry.to_prompt_text()

        user_roles_section = (
            "\n".join(
                f"- {role}"
                for role in requirements.user_roles
            )
            if requirements.user_roles
            else "None explicitly identified."
        )

        plan_lines = [
            "PROJECT PLAN",
            "------------",
        ]

        for index, milestone in enumerate(
            project_plan.milestones,
            start=1,
        ):
            plan_lines.append(
                f"MILESTONE M-{index:03d}: "
                f"{milestone.name}"
            )

            plan_lines.append(
                f"DESCRIPTION: "
                f"{milestone.description}"
            )

            plan_lines.append(
                "REQUIREMENT REFS: "
                + ", ".join(
                    milestone.requirement_refs
                )
            )

            for task in milestone.tasks:
                plan_lines.append(
                    f"TASK: [{', '.join(task.requirement_refs)}] "
                    f"{task.description}"
                )

        if project_plan.dependencies:
            plan_lines.append(
                "DEPENDENCIES:"
            )

            for dependency in project_plan.dependencies:
                plan_lines.append(
                    f"- {dependency}"
                )

        plan_lines.append(
            "DEVELOPMENT SEQUENCE: "
            + " -> ".join(
                project_plan.development_sequence
            )
        )

        return "\n\n".join(
            [
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
                    f"{user_roles_section}"
                ),
                requirement_section,
                "\n".join(
                    plan_lines
                ),
            ]
        )