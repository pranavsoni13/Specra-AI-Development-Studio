from app.core.llm.client import LocalLLMClient
from app.core.model_config import REQUIREMENT_ANALYST_MODEL

from .prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .quality import RequirementQualityController
from .schemas import RequirementAnalysis


MODEL_NAME = REQUIREMENT_ANALYST_MODEL


class RequirementAnalyst:
    """
    Requirement Analyst Agent.

    Converts a raw software idea into a validated
    RequirementAnalysis artifact.
    """

    def __init__(
        self,
        model_name: str = MODEL_NAME,
    ):
        self.llm_client = LocalLLMClient(
            model_name=model_name
        )

        self.quality_controller = (
            RequirementQualityController()
        )

    def analyze(
        self,
        idea: str,
        project_context: str | None = None,
    ) -> RequirementAnalysis:
        """
        Analyze a software idea using the shared LLM client.
        """

        if not idea or not idea.strip():
            raise ValueError(
                "Software idea cannot be empty."
            )

        context_text = (
            project_context.strip()
            if project_context and project_context.strip()
            else "No saved project context was supplied."
        )
        user_prompt = USER_PROMPT_TEMPLATE.format(
            idea=idea.strip(),
            project_context=context_text,
        )

        analysis = self.llm_client.generate_structured(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            output_schema=RequirementAnalysis,
        )

        return self.quality_controller.validate(
            analysis
        )