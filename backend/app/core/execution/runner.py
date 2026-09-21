from collections.abc import Callable
from typing import TypeVar
import time

from app.core.errors.exceptions import (
    AgentRetryExhaustedError,
)


T = TypeVar("T")


class AgentRunner:
    """
    Reusable execution and retry mechanism for AI agents.

    The operation receives validation feedback from the previous
    failed attempt so that the next LLM call can repair the artifact.
    """

    def __init__(
        self,
        max_attempts: int = 2,
    ):
        if max_attempts < 1:
            raise ValueError(
                "max_attempts must be at least 1."
            )

        self.max_attempts = max_attempts

    def run(
        self,
        operation: Callable[[str | None], T],
    ) -> T:
        previous_error: str | None = None

        total_start = time.perf_counter()

        for attempt in range(
            1,
            self.max_attempts + 1,
        ):
            attempt_start = time.perf_counter()

            print(
                f"\n[AgentRunner] Starting attempt {attempt}/"
                f"{self.max_attempts}..."
            )

            try:
                result = operation(previous_error)

                attempt_time = time.perf_counter() - attempt_start
                total_time = time.perf_counter() - total_start

                print(
                    f"[AgentRunner] Attempt {attempt} succeeded "
                    f"in {attempt_time:.2f}s "
                    f"(total: {total_time:.2f}s)"
                )

                return result

            except Exception as exc:
                attempt_time = time.perf_counter() - attempt_start

                previous_error = str(exc)

                print(
                    f"[AgentRunner] Attempt {attempt} failed "
                    f"after {attempt_time:.2f}s"
                )
                print(
                    f"[AgentRunner] Error: {previous_error}"
                )

                if attempt == self.max_attempts:
                    total_time = time.perf_counter() - total_start

                    print(
                        f"[AgentRunner] All attempts exhausted "
                        f"in {total_time:.2f}s"
                    )

                    raise AgentRetryExhaustedError(
                        f"Agent failed after "
                        f"{self.max_attempts} attempts: "
                        f"{previous_error}"
                    ) from exc

        raise AgentRetryExhaustedError(
            "Agent execution failed."
        )