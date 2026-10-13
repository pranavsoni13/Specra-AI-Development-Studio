"""Deterministic tests for provider-aware model configuration.

Run from backend/:
    python test_llm_provider_config.py
"""
import importlib
import os
import unittest
from unittest.mock import patch


from app.core import model_config


ROLE_VARIABLES = (
    "REQUIREMENT_ANALYST_MODEL",
    "PROJECT_PLANNER_MODEL",
    "SOFTWARE_ARCHITECT_MODEL",
    "TECHNICAL_REVIEWER_MODEL",
)
PROVIDER_ROLE_VARIABLES = tuple(
    f"{provider}_{role}"
    for provider in ("XAI", "OPENROUTER")
    for role in ROLE_VARIABLES
)


class ProviderModelConfigTests(unittest.TestCase):
    def _reload_with(self, **settings):
        clean = {
            "LLM_PROVIDER": "ollama",
            **{name: "" for name in ROLE_VARIABLES},
            **{name: "" for name in PROVIDER_ROLE_VARIABLES},
        }
        clean.update(settings)
        with patch.dict(os.environ, clean, clear=False):
            return importlib.reload(model_config)

    def tearDown(self):
        importlib.reload(model_config)

    def test_default_preserves_local_ollama_models(self):
        config = self._reload_with()
        self.assertEqual(config.LLM_PROVIDER, "ollama")
        self.assertEqual(config.REQUIREMENT_ANALYST_MODEL, "qwen3:1.7b")
        self.assertEqual(config.PROJECT_PLANNER_MODEL, "qwen3:4b")
        self.assertEqual(config.SOFTWARE_ARCHITECT_MODEL, "qwen3:4b")
        self.assertEqual(config.TECHNICAL_REVIEWER_MODEL, "qwen3:4b")

    def test_xai_uses_hosted_default_not_ollama_model_ids(self):
        config = self._reload_with(
            LLM_PROVIDER="xai",
            REQUIREMENT_ANALYST_MODEL="gemma4:cloud",
        )
        self.assertEqual(config.REQUIREMENT_ANALYST_MODEL, "grok-4.7")
        self.assertEqual(config.PROJECT_PLANNER_MODEL, "grok-4.7")

    def test_xai_role_override_takes_precedence(self):
        config = self._reload_with(
            LLM_PROVIDER="xai",
            XAI_TECHNICAL_REVIEWER_MODEL="grok-4.7",
        )
        self.assertEqual(config.TECHNICAL_REVIEWER_MODEL, "grok-4.7")

    def test_openrouter_uses_hosted_default_and_scoped_override(self):
        config = self._reload_with(
            LLM_PROVIDER="openrouter",
            OPENROUTER_SOFTWARE_ARCHITECT_MODEL="anthropic/claude-3.5-sonnet",
        )
        self.assertEqual(
            config.REQUIREMENT_ANALYST_MODEL,
            "openai/gpt-4o-mini",
        )
        self.assertEqual(
            config.SOFTWARE_ARCHITECT_MODEL,
            "anthropic/claude-3.5-sonnet",
        )

    def test_invalid_provider_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "LLM_PROVIDER"):
            self._reload_with(LLM_PROVIDER="unknown-provider")


if __name__ == "__main__":
    unittest.main()
