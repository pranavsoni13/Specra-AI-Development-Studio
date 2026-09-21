from typing import Type, TypeVar

import ollama
from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


class LocalLLMClient:
    """
    Shared interface for local structured LLM inference.

    Agents should use this class instead of calling Ollama directly.
    """

    def __init__(
        self,
        model_name: str = "qwen3:4b",
        num_predict: int = 3000,
        keep_alive: str = "30m",
    ):
        self.model_name = model_name
        self.num_predict = num_predict
        self.keep_alive = keep_alive

    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Type[T],
    ) -> T:

        response = ollama.chat(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            format=output_schema.model_json_schema(),
            think=False,
            stream=False,
            keep_alive=self.keep_alive,
            options={
                "temperature": 0,
                "num_predict": self.num_predict,
            },
        )

        content = response.message.content

        if not content:
            raise RuntimeError(
                "LLM returned an empty response."
            )

        return output_schema.model_validate_json(content)