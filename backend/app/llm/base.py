"""LLM provider interface (Step 10 — AI Query).

Mirrors the Step 9 embedding-provider abstraction: implementations are
swappable without touching retrieval or business logic, availability is
probed without side effects, and no provider ever fabricates content —
answers are generated ONLY from the evidence passed in the prompt.

No cloud provider is hard-coded into business logic; the concrete provider
comes from configuration (`settings.llm_*`), keys stay in the environment.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMCompletion:
    """One real completion plus the identity that produced it."""

    text: str
    provider: str
    model: str
    # Observability (safe metadata only — never includes keys/URLs).
    prompt_chars: int
    completion_chars: int


class LLMProviderError(RuntimeError):
    """The provider failed for a real reason (HTTP error, timeout, malformed body)."""


class LLMProviderUnavailableError(RuntimeError):
    """No usable LLM provider is configured in this environment."""


class LLMProvider(ABC):
    """Interface for answer-generation backends."""

    name: str = ""
    model: str = ""

    @abstractmethod
    def is_available(self) -> bool:
        """Whether this provider can run right now (no downloads, no key logging)."""

    @abstractmethod
    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        timeout_seconds: float,
        max_output_chars: int,
    ) -> LLMCompletion:
        """Generate one completion from structured messages.

        `messages` is a list of {"role": ..., "content": ...} dicts. Raises
        LLMProviderError on failure (the message never contains secrets).
        """
