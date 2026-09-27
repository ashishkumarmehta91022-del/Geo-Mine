"""Embedding provider interface.

Implementations must be deterministic for the same model+input. A provider
either returns real vectors or raises — never returns placeholder/random
values. Swapping providers never changes search or business logic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingResult:
    """One batch of real vectors plus the identity that produced them."""

    vectors: list[list[float]]
    provider: str
    model: str
    dimensions: int


class EmbeddingProviderError(RuntimeError):
    """The provider failed for a real reason (load error, timeout...)."""


class EmbeddingProviderUnavailableError(RuntimeError):
    """No usable embedding provider exists in this environment."""


class EmbeddingProvider(ABC):
    """Interface for embedding backends (local ONNX today, others later)."""

    name: str = ""
    model: str = ""
    dimensions: int = 0

    @abstractmethod
    def is_available(self) -> bool:
        """Whether this provider can run right now (no downloads triggered)."""

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> EmbeddingResult:
        """Embed a batch of texts. Raises on failure; never fabricates vectors."""
