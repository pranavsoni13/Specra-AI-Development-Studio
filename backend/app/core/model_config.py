import os
from typing import Final


LLM_PROVIDER: Final[str] = (
    os.getenv("LLM_PROVIDER", "ollama").strip().lower() or "ollama"
)

if LLM_PROVIDER not in {"ollama", "xai", "openrouter"}:
    raise ValueError(
        "LLM_PROVIDER must be one of: ollama, xai, openrouter."
    )


def _configured_model(
    role: str,
    local_default: str,
    hosted_default: str,
) -> str:
    """Resolve a role model without reusing an incompatible provider's model ID.

    Ollama keeps the original role-specific variables for backwards
    compatibility. Hosted providers may use provider-scoped variables such as
    XAI_REQUIREMENT_ANALYST_MODEL or OPENROUTER_REQUIREMENT_ANALYST_MODEL.
    """
    if LLM_PROVIDER == "ollama":
        value = os.getenv(role, "").strip()
        return value or local_default

    provider_variable = f"{LLM_PROVIDER.upper()}_{role}"
    value = os.getenv(provider_variable, "").strip()
    return value or hosted_default


REQUIREMENT_ANALYST_MODEL: Final[str] = _configured_model(
    "REQUIREMENT_ANALYST_MODEL",
    "qwen3:1.7b",
    "grok-4.7" if LLM_PROVIDER == "xai" else x-ai/grok-4.7,
)
PROJECT_PLANNER_MODEL: Final[str] = _configured_model(
    "PROJECT_PLANNER_MODEL",
    "qwen3:4b",
    "grok-4.7" if LLM_PROVIDER == "xai" else x-ai/grok-4.7,
)
SOFTWARE_ARCHITECT_MODEL: Final[str] = _configured_model(
    "SOFTWARE_ARCHITECT_MODEL",
    "qwen3:4b",
    "grok-4.7" if LLM_PROVIDER == "xai" else x-ai/grok-4.7,
)
TECHNICAL_REVIEWER_MODEL: Final[str] = _configured_model(
    "TECHNICAL_REVIEWER_MODEL",
    "qwen3:4b",
    "grok-4.7" if LLM_PROVIDER == "xai" else x-ai/grok-4.7,
)
