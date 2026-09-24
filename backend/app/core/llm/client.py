from typing import Type, TypeVar

import ollama
from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


class LocalLLMClient:
    def __init__(
        self,
        model_name: str = "qwen3:4b",
        num_predict: int = 3000,
        keep_alive: str = "30m",
        debug: bool = True,
    ):
        self.model_name = model_name
        self.num_predict = num_predict
        self.keep_alive = keep_alive
        self.debug = debug

    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Type[T],
    ) -> T:

        if not system_prompt.strip():
            raise ValueError("System prompt cannot be empty.")

        if not user_prompt.strip():
            raise ValueError("User prompt cannot be empty.")

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

        if self.debug:
            self._print_metrics(
                response=response,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output=content,
            )

        try:
            return output_schema.model_validate_json(content)
        except Exception as exc:
            raise RuntimeError(
                "LLM returned content that could not be validated "
                "against the requested output schema."
            ) from exc

    def _print_metrics(
        self,
        response,
        system_prompt: str,
        user_prompt: str,
        output: str,
    ) -> None:

        prompt_chars = len(system_prompt) + len(user_prompt)
        output_chars = len(output)

        prompt_eval_count = getattr(
            response,
            "prompt_eval_count",
            None,
        )

        eval_count = getattr(
            response,
            "eval_count",
            None,
        )

        prompt_eval_duration = getattr(
            response,
            "prompt_eval_duration",
            None,
        )

        eval_duration = getattr(
            response,
            "eval_duration",
            None,
        )

        total_duration = getattr(
            response,
            "total_duration",
            None,
        )

        def seconds(value):
            if value is None:
                return None

            return value / 1_000_000_000

        prompt_seconds = seconds(prompt_eval_duration)
        generation_seconds = seconds(eval_duration)
        total_seconds = seconds(total_duration)

        generation_tps = None

        if eval_count and generation_seconds and generation_seconds > 0:
            generation_tps = eval_count / generation_seconds

        print("\n[LLM Diagnostics]")
        print(f"Model: {self.model_name}")
        print(f"Prompt characters: {prompt_chars}")
        print(f"Output characters: {output_chars}")

        if prompt_eval_count is not None:
            print(f"Prompt tokens: {prompt_eval_count}")

        if eval_count is not None:
            print(f"Output tokens: {eval_count}")

        if prompt_seconds is not None:
            print(
                f"Prompt evaluation: {prompt_seconds:.2f}s"
            )

        if generation_seconds is not None:
            print(
                f"Generation: {generation_seconds:.2f}s"
            )

        if total_seconds is not None:
            print(
                f"Total Ollama time: {total_seconds:.2f}s"
            )

        if generation_tps is not None:
            print(
                f"Generation speed: {generation_tps:.2f} tokens/sec"
            )

        print()