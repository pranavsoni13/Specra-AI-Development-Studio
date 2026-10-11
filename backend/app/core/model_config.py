import os
from typing import Final


def _configured_model(variable: str, default: str) -> str:
    value = os.getenv(variable, default).strip()
    return value or default


# Local development keeps the existing Qwen defaults. Hosted deployments can
# override each stage independently through environment variables.
REQUIREMENT_ANALYST_MODEL: Final[str] = _configured_model(
    "REQUIREMENT_ANALYST_MODEL", "qwen3:1.7b"
)
PROJECT_PLANNER_MODEL: Final[str] = _configured_model(
    "PROJECT_PLANNER_MODEL", "qwen3:4b"
)
SOFTWARE_ARCHITECT_MODEL: Final[str] = _configured_model(
    "SOFTWARE_ARCHITECT_MODEL", "qwen3:4b"
)
TECHNICAL_REVIEWER_MODEL: Final[str] = _configured_model(
    "TECHNICAL_REVIEWER_MODEL", "qwen3:4b"
)
