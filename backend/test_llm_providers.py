import os
import unittest
from unittest.mock import patch

from pydantic import BaseModel

from app.core.llm.client import LocalLLMClient


class ExampleOutput(BaseModel):
    answer: str


class ProviderConfigurationTests(unittest.TestCase):
    def test_ollama_remains_default(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "app.core.llm.client.ollama.Client"
        ) as ollama_client:
            client = LocalLLMClient(debug=False)
        self.assertEqual(client.provider, "ollama")
        ollama_client.assert_called_once_with()

    def test_openrouter_requires_server_side_key(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "openrouter"}, clear=True):
            with self.assertRaisesRegex(ValueError, "OPENROUTER_API_KEY"):
                LocalLLMClient(debug=False)

    def test_xai_requires_server_side_key(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "xai"}, clear=True):
            with self.assertRaisesRegex(ValueError, "XAI_API_KEY"):
                LocalLLMClient(debug=False)

    def test_unknown_provider_is_rejected(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "unknown"}, clear=True):
            with self.assertRaisesRegex(ValueError, "Unsupported LLM_PROVIDER"):
                LocalLLMClient(debug=False)

    def test_openrouter_uses_compatible_endpoint(self):
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "openrouter",
                "OPENROUTER_API_KEY": "test-key",
            },
            clear=True,
        ), patch("app.core.llm.client.OpenAI") as openai_client:
            client = LocalLLMClient(model_name="openai/test-model", debug=False)
        self.assertEqual(client.provider, "openrouter")
        openai_client.assert_called_once()
        self.assertEqual(
            openai_client.call_args.kwargs["base_url"],
            "https://openrouter.ai/api/v1",
        )

    def test_xai_uses_compatible_endpoint(self):
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "xai",
                "XAI_API_KEY": "test-key",
            },
            clear=True,
        ), patch("app.core.llm.client.OpenAI") as openai_client:
            client = LocalLLMClient(model_name="grok-4.7", debug=False)
        self.assertEqual(client.provider, "xai")
        openai_client.assert_called_once()
        self.assertEqual(
            openai_client.call_args.kwargs["base_url"],
            "https://api.x.ai/v1",
        )

    def test_remote_json_is_validated_by_existing_schema(self):
        parsed = LocalLLMClient._validate_output(
            '{"answer":"Specra"}',
            ExampleOutput,
        )
        self.assertEqual(parsed.answer, "Specra")

    def test_invalid_remote_json_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "ExampleOutput"):
            LocalLLMClient._validate_output(
                '{"answer":42}',
                ExampleOutput,
            )


if __name__ == "__main__":
    unittest.main()
