class AgentExecutionError(Exception):
    """Base exception for agent execution failures."""


class LLMGenerationError(AgentExecutionError):
    """Raised when the LLM cannot generate a usable response."""


class ArtifactValidationError(AgentExecutionError):
    """Raised when an artifact fails validation."""


class AgentRetryExhaustedError(AgentExecutionError):
    """Raised when an agent fails after all retry attempts."""