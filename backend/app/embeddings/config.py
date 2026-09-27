"""Embedding configuration — bounded, explicit, env-overridable.

No cloud provider is configured; the local fastembed model is the default
when installed. All guardrails live here so safeguards are testable.
"""

from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class EmbeddingConfig:
    """Guardrails + model identity for the embedding layer."""

    # BAAI/bge-small-en-v1.5 via fastembed: local ONNX inference, 384 dims,
    # cached locally after a one-time download (no runtime API keys).
    provider: str = "fastembed"
    model: str = "BAAI/bge-small-en-v1.5"
    dimensions: int = 384
    # Max characters of context text per embedding input (beyond this, truncate).
    max_input_chars: int = 4000
    # Max units embedded in one batch call (bounded memory).
    max_batch_size: int = 32
    # Max units embedded per document run (cost/runtime guardrail).
    max_units_per_document: int = 500
    # Wall-clock cap for one provider batch call.
    timeout_seconds: float = 120.0

    @classmethod
    def from_settings(cls) -> "EmbeddingConfig":
        """Env-overridable variant (EMBEDDING_* variables in .env)."""
        return cls(
            max_input_chars=settings.embedding_max_input_chars,
            max_batch_size=settings.embedding_max_batch_size,
            max_units_per_document=settings.embedding_max_units_per_document,
            timeout_seconds=settings.embedding_timeout_seconds,
        )


def default_config() -> EmbeddingConfig:
    return EmbeddingConfig.from_settings()
