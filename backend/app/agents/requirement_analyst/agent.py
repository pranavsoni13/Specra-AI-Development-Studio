from ollama import chat
from pydantic import ValidationError

from .prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .schemas import RequirementAnalysis
from .quality import RequirementQualityController


MODEL_NAME = "qwen3:4b"


class RequirementAnalyst:
    """
    Requirement Analyst Agent.

    Converts a raw software idea into a validated
    RequirementAnalysis object using a local Ollama model.
    """

    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self.quality_controller = RequirementQualityController()

    def analyze(self, idea: str) -> RequirementAnalysis:
        """
        Analyze a software idea and return a quality-checked
        RequirementAnalysis object.
        """

        if not idea or not idea.strip():
            raise ValueError("Software idea cannot be empty.")

        user_prompt = USER_PROMPT_TEMPLATE.format(
            idea=idea.strip()
        )

        response = chat(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            format=RequirementAnalysis.model_json_schema(),
            think=False,
            stream=False,
            options={
                "temperature": 0,
            },
        )

        raw_content = response.message.content

        if not raw_content:
            raise RuntimeError(
                "Ollama returned an empty response."
            )

        try:
            analysis = RequirementAnalysis.model_validate_json(
                raw_content
            )
        except ValidationError as exc:
            raise RuntimeError(
                f"Model returned invalid requirement data: {exc}"
            ) from exc

        return self.quality_controller.validate(analysis)