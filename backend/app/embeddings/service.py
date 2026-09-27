"""Embedding service: provider access, availability and bounded batching."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError

from app.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingProviderUnavailableError,
    EmbeddingResult,
)
from app.embeddings.config import EmbeddingConfig
from app.embeddings.fastembed_provider import FastEmbedProvider

logger = logging.getLogger(__name__)

_default_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    """Return the process-wide provider (lazy singleton)."""
    global _default_provider
    if _default_provider is None:
        _default_provider = FastEmbedProvider()
    return _default_provider


def set_embedding_provider(provider: EmbeddingProvider | None) -> None:
    """Replace the default provider (tests inject fakes here)."""
    global _default_provider
    _default_provider = provider


def embedding_available() -> bool:
    """Whether a usable provider exists in this environment (no downloads)."""
    return get_embedding_provider().is_available()


def embed_texts(
    texts: list[str], config: EmbeddingConfig
) -> tuple[EmbeddingResult | None, str | None]:
    """Embed texts in bounded batches with a wall-clock timeout.

    Returns (result, error): exactly one is None.
      - result: real vectors from the provider
      - error:  "unavailable: …" (no provider) or "failed: …" (provider error/timeout)

    Never fabricates vectors.
    """
    if not texts:
        return None, "no texts to embed"

    provider = get_embedding_provider()
    if not provider.is_available():
        return None, "unavailable: no usable embedding provider in this environment"

    bounded = [t[: config.max_input_chars] for t in texts]
    batches = [
        bounded[i : i + config.max_batch_size]
        for i in range(0, len(bounded), config.max_batch_size)
    ]

    try:
        all_vectors: list[list[float]] = []
        for batch in batches:
            executor = ThreadPoolExecutor(max_workers=1)
            try:
                future = executor.submit(provider.embed_batch, batch)
                result = future.result(timeout=config.timeout_seconds)
            except FutureTimeoutError:
                raise EmbeddingProviderError(
                    f"Embedding batch timed out after {config.timeout_seconds}s"
                ) from None
            finally:
                executor.shutdown(wait=False)
            all_vectors.extend(result.vectors)
            if len(all_vectors) > len(texts):  # defensive: engine returned too many
                raise EmbeddingProviderError("Embedding engine returned unexpected extra vectors.")
        return (
            EmbeddingResult(
                vectors=all_vectors,
                provider=result.provider,
                model=result.model,
                dimensions=result.dimensions,
            ),
            None,
        )
    except EmbeddingProviderUnavailableError as exc:
        return None, f"unavailable: {exc}"
    except EmbeddingProviderError as exc:
        return None, f"failed: {exc}"


def timed_embed(texts: list[str], config: EmbeddingConfig) -> tuple[EmbeddingResult | None, str | None, float]:
    """embed_texts + elapsed seconds (observability, used by the indexing service)."""
    start = time.monotonic()
    result, error = embed_texts(texts, config)
    return result, error, time.monotonic() - start
