"""Mocked provider contract tests; they never make external API calls.

Run from backend/:
    python test_llm_client_providers.py
"""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import BaseModel

from app.core.llm.client import LocalLLMClient


class TinyOutput(BaseModel):
    message: str


def fake_response(content: str):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
            )
        ],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


class LLMProviderClientTests(unittest.TestCase):
    def test_local_ollama_path_is_preserved(self):
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "ollama",
                "OLLAMA_HOST": "",
                "OLLAMA_API_KEY": "",
            },
            clear=False,
        ), patch("ollama.Client") as ollama_client_factory:
            ollama_client_factory.return_value.chat.return_value = (
                SimpleNamespace(
                    message=SimpleNamespace(content='{"message":"local"}'),
                    prompt_eval_count=10,
                    eval_count=5,
                    prompt_eval_duration=1000000,
                    eval_duration=1000000,
                    total_duration=2000000,
                )
            )
            client = LocalLLMClient(model_name="qwen3:4b", debug=False)
            result = client.generate_structured(
                "Return a short answer.",
                "Say local.",
                TinyOutput,
            )

        self.assertEqual(result.message, "local")
        ollama_client_factory.return_value.chat.assert_called_once()
        kwargs = ollama_client_factory.return_value.chat.call_args.kwargs
        self.assertIn("format", kwargs)
        self.assertEqual(kwargs["model"], "qwen3:4b")

    def test_xai_uses_expected_endpoint_and_validates_json(self):
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "xai",
                "XAI_API_KEY": "test-key-not-real",
                "LLM_API_KEY": "",
                "LLM_BASE_URL": "",
            },
            clear=False,
        ), patch("app.core.llm.client.OpenAI") as openai_factory:
            openai_factory.return_value.chat.completions.create.return_value = (
                fake_response('{"message":"from xai"}')
            )
            client = LocalLLMClient(model_name="grok-4.7", debug=False)
            result = client.generate_structured(
                "Return a short answer.",
                "Say from xai.",
                TinyOutput,
            )

        self.assertEqual(result.message, "from xai")
        options = openai_factory.call_args.kwargs
        self.assertEqual(options["api_key"], "test-key-not-real")
        self.assertEqual(options["base_url"], "https://api.x.ai/v1")
        request = openai_factory.return_value.chat.completions.create.call_args.kwargs
        self.assertEqual(request["model"], "grok-4.7")
        self.assertEqual(request["response_format"]["type"], "json_schema")

    def test_openrouter_sets_routing_metadata(self):
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "openrouter",
                "OPENROUTER_API_KEY": "test-key-not-real",
                "LLM_API_KEY": "",
                "LLM_BASE_URL": "",
            },
            clear=False,
        ), patch("app.core.llm.client.OpenAI") as openai_factory:
            openai_factory.return_value.chat.completions.create.return_value = (
                fake_response('{"message":"from router"}')
            )
            client = LocalLLMClient(
                model_name="x-ai/grok-4.7",
                debug=False,
            )
            result = client.generate_structured(
                "Return a short answer.",
                "Say from router.",
                TinyOutput,
            )

        self.assertEqual(result.message, "from router")
        options = openai_factory.call_args.kwargs
        self.assertEqual(
            options["base_url"],
            "https://openrouter.ai/api/v1",
        )
        self.assertEqual(
            options["default_headers"]["X-OpenRouter-Title"],
            "Specra AI Development Studio",
        )

    def test_hosted_provider_requires_key(self):
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "xai",
                "XAI_API_KEY": "",
                "LLM_API_KEY": "",
            },
            clear=False,
        ):
            with self.assertRaisesRegex(ValueError, "XAI_API_KEY"):
                LocalLLMClient(debug=False)


if __name__ == "__main__":
    unittest.main()
