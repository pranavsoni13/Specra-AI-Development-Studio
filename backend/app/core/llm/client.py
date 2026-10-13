import json
import os
import re
from typing import Type, TypeVar
from urllib.parse import urlparse

import ollama
from pydantic import BaseModel, ValidationError


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
        self.provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower() or "ollama"
        self._openai_client = None

        if self.provider not in {"ollama", "xai", "openrouter"}:
            raise ValueError(
                "LLM_PROVIDER must be one of: ollama, xai, openrouter."
            )

        if self.provider in {"xai", "openrouter"}:
            # Both providers expose OpenAI-compatible chat completions.
            from openai import OpenAI

            api_key_env = (
                "XAI_API_KEY" if self.provider == "xai"
                else "OPENROUTER_API_KEY"
            )
            api_key = (
                os.getenv(api_key_env, "").strip()
                or os.getenv("LLM_API_KEY", "").strip()
            )
            if not api_key:
                raise RuntimeError(
                    f"LLM_PROVIDER='{self.provider}' requires {api_key_env} "
                    "or LLM_API_KEY to be set in the server environment."
                )

            default_base_url = (
                "https://api.x.ai/v1"
                if self.provider == "xai"
                else "https://openrouter.ai/api/v1"
            )
            base_url = (
                os.getenv("LLM_BASE_URL", "").strip()
                or default_base_url
            )
            client_options = {
                "api_key": api_key,
                "base_url": base_url,
                "timeout": 180.0,
            }
            if self.provider == "openrouter":
                client_options["default_headers"] = {
                    "HTTP-Referer": "https://specra-ai-development-studio.vercel.app",
                    "X-Title": "Specra AI Development Studio",
                }
            self._openai_client = OpenAI(**client_options)
            return

        # When OLLAMA_HOST is set, connect to that host explicitly.
        host = os.getenv("OLLAMA_HOST", "").strip()
        api_key = os.getenv("OLLAMA_API_KEY", "").strip()
        host_name = (urlparse(host).hostname or "").casefold() if host else ""
        self._is_ollama_cloud = host_name in {
            "ollama.com",
            "www.ollama.com",
        }

        if host:
            headers = (
                {"Authorization": f"Bearer {api_key}"}
                if api_key
                else {}
            )
            self._ollama_client = ollama.Client(
                host=host,
                headers=headers,
            )
        else:
            self._ollama_client = ollama.Client()

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

        schema = output_schema.model_json_schema()

        if self.provider in {"xai", "openrouter"}:
            return self._generate_openai_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_schema=output_schema,
                schema=schema,
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        request_options = {}

        if self._is_ollama_cloud:
            # Ollama Cloud currently does not support the format/schema
            # argument. Put the schema in the prompt and validate locally.
            schema_text = json.dumps(
                schema,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            messages[0]["content"] += (
                "\n\nSTRICT OUTPUT CONTRACT:\n"
                "Return exactly one JSON object matching the JSON Schema "
                "provided in the user's message. Do not return Markdown, "
                "code fences, reasoning, or commentary. Include every "
                "required field using the correct JSON types. Do not add "
                "fields that are not allowed by the schema."
            )
            messages[1]["content"] += (
                "\n\nOUTPUT JSON SCHEMA (follow this schema exactly):\n"
                f"{schema_text}\n"
                "Return only the JSON object, with no surrounding text."
            )
        else:
            # Local Ollama supports native constrained structured output.
            request_options["format"] = schema

        response = self._ollama_client.chat(
            model=self.model_name,
            messages=messages,
            think=False,
            stream=False,
            keep_alive=self.keep_alive,
            options={
                "temperature": 0,
                "num_predict": self.num_predict,
            },
            **request_options,
        )

        content = response.message.content
        if not content:
            raise RuntimeError("LLM returned an empty response.")

        if self.debug:
            self._print_metrics(
                response=response,
                system_prompt=messages[0]["content"],
                user_prompt=messages[1]["content"],
                output=content,
            )

        return self._validate_output(content, output_schema)

    def _generate_openai_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Type[T],
        schema: dict,
    ) -> T:
        """Generate schema-validated JSON with xAI or OpenRouter."""
        schema_text = json.dumps(
            schema,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        messages = [
            {
                "role": "system",
                "content": (
                    system_prompt
                    + "\n\nReturn only a JSON object matching the "
                    "schema provided with this request."
                ),
            },
            {
                "role": "user",
                "content": (
                    user_prompt
                    + "\n\nOUTPUT JSON SCHEMA (follow exactly):\n"
                    + schema_text
                    + "\nReturn only the JSON object. Do not wrap it in Markdown."
                ),
            },
        ]

        request = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0,
            "max_tokens": self.num_predict,
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": output_schema.__name__.lower(),
                    "strict": True,
                    "schema": schema,
                },
            },
        }

        try:
            response = self._openai_client.chat.completions.create(**request)
        except Exception as exc:
            # Some OpenAI-compatible models do not implement strict JSON
            # Schema mode. Retry only on a provider's explicit HTTP 400 response
            # using JSON-object mode; authentication, rate-limit, and server
            # errors should remain visible to the caller.
            from openai import BadRequestError

            if not isinstance(exc, BadRequestError):
                raise
            request["response_format"] = {"type": "json_object"}
            response = self._openai_client.chat.completions.create(**request)

        choices = getattr(response, "choices", None) or []
        content = (
            getattr(getattr(choices[0], "message", None), "content", None)
            if choices else None
        )
        if not content:
            raise RuntimeError(
                f"{self.provider} returned an empty response for model "
                f"'{self.model_name}'."
            )

        if self.debug:
            usage = getattr(response, "usage", None)
            print("\n[LLM Diagnostics]")
            print(f"Provider: {self.provider}")
            print(f"Model: {self.model_name}")
            print(
                "Prompt characters: "
                f"{len(messages[0]['content']) + len(messages[1]['content'])}"
            )
            print(f"Output characters: {len(content)}")
            if usage is not None:
                prompt_tokens = getattr(usage, "prompt_tokens", None)
                output_tokens = getattr(usage, "completion_tokens", None)
                if prompt_tokens is not None:
                    print(f"Prompt tokens: {prompt_tokens}")
                if output_tokens is not None:
                    print(f"Output tokens: {output_tokens}")

        return self._validate_output(content, output_schema)

    @staticmethod
    def _validate_output(content: str, output_schema: Type[T]) -> T:
        try:
            return output_schema.model_validate_json(content)
        except Exception as exc:
            direct_error = exc

        # Hosted models can add a preamble or Markdown fences. Extract JSON
        # candidates, but accept only one that passes the original schema.
        decoder = json.JSONDecoder()
        validation_errors = []

        for match in re.finditer(r"[{\[]", content):
            try:
                candidate, _ = decoder.raw_decode(content[match.start():])
            except json.JSONDecodeError:
                continue

            if not isinstance(candidate, dict):
                continue

            try:
                return output_schema.model_validate(candidate)
            except ValidationError as exc:
                validation_errors.append(exc)

        if validation_errors:
            latest = validation_errors[-1]
            details = "; ".join(
                f"{'.'.join(str(part) for part in item['loc']) or '<root>'}: "
                f"{item['msg']}"
                for item in latest.errors()[:8]
            )
        else:
            details = "response was not valid JSON matching the expected object"

        raise RuntimeError(
            f"LLM output failed the {output_schema.__name__} schema: {details}"
        ) from direct_error

    def _print_metrics(
        self,
        response,
        system_prompt: str,
        user_prompt: str,
        output: str,
    ) -> None:
        prompt_chars = len(system_prompt) + len(user_prompt)
        output_chars = len(output)
        prompt_eval_count = getattr(response, "prompt_eval_count", None)
        eval_count = getattr(response, "eval_count", None)
        prompt_eval_duration = getattr(response, "prompt_eval_duration", None)
        eval_duration = getattr(response, "eval_duration", None)
        total_duration = getattr(response, "total_duration", None)

        def seconds(value):
            return None if value is None else value / 1_000_000_000

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
            print(f"Prompt evaluation: {prompt_seconds:.2f}s")
        if generation_seconds is not None:
            print(f"Generation: {generation_seconds:.2f}s")
        if total_seconds is not None:
            print(f"Total Ollama time: {total_seconds:.2f}s")
        if generation_tps is not None:
            print(f"Generation speed: {generation_tps:.2f} tokens/sec")
        print()
