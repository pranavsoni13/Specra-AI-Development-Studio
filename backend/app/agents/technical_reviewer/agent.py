from app.core.execution.runner import AgentRunner
from app.core.llm.client import LocalLLMClient

from app.agents.project_planner.schemas import ProjectPlan
from app.agents.requirement_analyst.schemas import RequirementAnalysis
from app.agents.software_architect.schemas import SystemArchitecture

from .prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .quality import TechnicalReviewQualityController
from .schemas import ReviewReport


MODEL_NAME = "qwen3:4b"


class TechnicalReviewer:
    """
    Technical Reviewer Agent.

    Reviews the requirements, project plan, and system architecture
    for coverage, consistency, unsupported additions, and traceability.
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

        requirements_json = (
            requirements.model_dump_json(indent=2)
        )

        project_plan_json = (
            project_plan.model_dump_json(indent=2)
        )

        architecture_json = (
            architecture.model_dump_json(indent=2)
        )

        def execute(
            previous_error: str | None,
        ) -> ReviewReport:

            user_prompt = USER_PROMPT_TEMPLATE.format(
                requirements=requirements_json,
                project_plan=project_plan_json,
                architecture=architecture_json,
            )

            if previous_error:
                user_prompt += f"""

The previous review report was rejected by the
quality controller.

Validation feedback:
{previous_error}

Regenerate the complete ReviewReport.

Make sure:
- Every functional requirement has exactly one coverage entry.
- Coverage values match the actual ProjectPlan and SystemArchitecture.
- Do not mark PASS when high or critical findings exist.
- Every finding contains evidence and a recommendation.
"""
            
            report = self.llm_client.generate_structured(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                output_schema=ReviewReport,
            )

            return self.quality_controller.validate(
                report,
                requirements,
                project_plan,
                architecture,
            )

        return self.runner.run(execute)