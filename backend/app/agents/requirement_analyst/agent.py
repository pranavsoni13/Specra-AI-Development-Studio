from app.core.llm.client import LocalLLMClient

from .prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .quality import RequirementQualityController
from .schemas import RequirementAnalysis


MODEL_NAME = "qwen3:4b"


class RequirementAnalyst:
    """
    Requirement Analyst Agent.

    Converts a raw software idea into a validated
    RequirementAnalysis artifact.
    """

    def __init__(self, model_name: str = MODEL_NAME):
        self.llm_client = LocalLLMClient(
            model_name=model_name
        )
        self.quality_controller = RequirementQualityController()

    def analyze(
        self,
        idea: str,
    ) -> RequirementAnalysis:
        """
        Analyze a software idea using the shared LLM client.
        """

        if not idea or not idea.strip():
            raise ValueError(
                "Software idea cannot be empty."
            )

        user_prompt = USER_PROMPT_TEMPLATE.format(
            idea=idea.strip()
        )

        analysis = self.llm_client.generate_structured(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            output_schema=RequirementAnalysis,
        )

        return self.quality_controller.validate(
            analysis
        )