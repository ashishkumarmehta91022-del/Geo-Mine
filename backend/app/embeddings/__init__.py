"""Embedding layer (Step 9): pluggable providers + deterministic input builder.

No fake vectors, ever: when no provider is usable the layer reports an
explicit unavailable state. Vectors are stored as JSONB on knowledge_index
(pgvector conversion is a later migration when PostgreSQL is available).
"""

from app.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingProviderUnavailableError,
    EmbeddingResult,
)
from app.embeddings.config import EmbeddingConfig, default_config
from app.embeddings.inputs import build_embedding_input
from app.embeddings.service import (
    embed_texts,
    embedding_available,
    get_embedding_provider,
    set_embedding_provider,
    timed_embed,
)

__all__ = [
    "EmbeddingProvider",
    "EmbeddingProviderError",
    "EmbeddingProviderUnavailableError",
    "EmbeddingResult",
    "EmbeddingConfig",
    "default_config",
    "build_embedding_input",
    "embed_texts",
    "embedding_available",
    "get_embedding_provider",
    "set_embedding_provider",
    "timed_embed",
]
