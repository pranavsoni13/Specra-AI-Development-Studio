import os
from typing import Final


def _configured_model(variable: str, default: str) -> str:
    value = os.getenv(variable, default).strip()
    return value or default


# The local setup stays the default. Remote provider defaults can be overridden
# globally or per agent with the environment variables documented in docs/LLM_PROVIDERS.md.
_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").strip().lower()

if _PROVIDER == "xai":
    _DEFAULT_MODEL = _configured_model("XAI_MODEL", "grok-4.7")
elif _PROVIDER == "openrouter":
    _DEFAULT_MODEL = _configured_model(
        "OPENROUTER_MODEL",
        "x-ai/grok-4.7",
    )
else:
    _DEFAULT_MODEL = "qwen3:4b"

REQUIREMENT_ANALYST_MODEL: Final[str] = _configured_model(
    "REQUIREMENT_ANALYST_MODEL",
    "qwen3:1.7b" if _PROVIDER == "ollama" else _DEFAULT_MODEL,
)
PROJECT_PLANNER_MODEL: Final[str] = _configured_model(
    "PROJECT_PLANNER_MODEL",
    _DEFAULT_MODEL,
)
SOFTWARE_ARCHITECT_MODEL: Final[str] = _configured_model(
    "SOFTWARE_ARCHITECT_MODEL",
    _DEFAULT_MODEL,
)
TECHNICAL_REVIEWER_MODEL: Final[str] = _configured_model(
    "TECHNICAL_REVIEWER_MODEL",
    _DEFAULT_MODEL,
)
