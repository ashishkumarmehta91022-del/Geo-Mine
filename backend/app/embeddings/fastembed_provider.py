"""Concrete embedding provider: fastembed (local ONNX inference).

Model: BAAI/bge-small-en-v1.5 (384 dims, unit-normalized). Weights are
downloaded once from the Hugging Face CDN at first use, then cached locally —
after that the provider runs fully offline with no API keys. Availability is
probed WITHOUT triggering a download; the model loads lazily on first embed.
"""

import logging
import threading
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version

from app.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingProviderUnavailableError,
    EmbeddingResult,
)

logger = logging.getLogger(__name__)

PROVIDER_NAME = "fastembed"
MODEL_NAME = "BAAI/bge-small-en-v1.5"
MODEL_DIMENSIONS = 384


def _installed_version() -> str:
    try:
        return package_version("fastembed")
    except PackageNotFoundError:
        return "unknown"


class FastEmbedProvider(EmbeddingProvider):
    """Lazy-singleton provider. Deterministic for the same model + input."""

    name = PROVIDER_NAME
    model = MODEL_NAME
    dimensions = MODEL_DIMENSIONS

    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        """True when fastembed is importable. Does NOT download the model."""
        try:
            import fastembed  # noqa: F401

            return True
        except ImportError:
            return False

    def _ensure_model(self):
        if self._model is None:
            with self._lock:  # double-checked: one download/load, once
                if self._model is None:
                    try:
                        from fastembed import TextEmbedding

                        logger.info("Loading embedding model %s (first use may download weights)", self.model)
                        self._model = TextEmbedding(model_name=self.model)
                    except ImportError as exc:
                        raise EmbeddingProviderUnavailableError(
                            "fastembed is not installed in this environment."
                        ) from exc
                    except Exception as exc:  # noqa: BLE001 — download/load failures surface honestly
                        raise EmbeddingProviderError(
                            f"Could not load embedding model {self.model}: "
                            f"{exc.__class__.__name__}: {exc}"
                        ) from exc
        return self._model

    def embed_batch(self, texts: list[str]) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(
                vectors=[], provider=self.name, model=self.model, dimensions=self.dimensions
            )
        model = self._ensure_model()
        try:
            vectors = [vector.tolist() for vector in model.embed(texts)]
        except Exception as exc:  # noqa: BLE001 — real failures propagate
            raise EmbeddingProviderError(
                f"Embedding failed: {exc.__class__.__name__}: {exc}"
            ) from exc
        if len(vectors) != len(texts):  # engine contract check, never pad silently
            raise EmbeddingProviderError(
                f"Embedding engine returned {len(vectors)} vectors for {len(texts)} inputs."
            )
        return EmbeddingResult(
            vectors=vectors, provider=self.name, model=self.model, dimensions=self.dimensions
        )


def provider_version() -> str:
    return _installed_version()
