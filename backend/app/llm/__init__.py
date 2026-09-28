"""LLM provider layer (Step 10 — AI Query).

Pluggable answer-generation abstraction mirroring Step 9's embedding
provider: business logic never references a concrete vendor. Availability
probing is side-effect-free; keys live only in configuration/environment.
"""

from app.llm.base import (
    LLMCompletion,
    LLMProvider,
    LLMProviderError,
    LLMProviderUnavailableError,
)
from app.llm.config import LLMConfig, default_config
from app.llm.service import (
    generate_completion,
    get_llm_provider,
    llm_available,
    set_llm_provider,
)

__all__ = [
    "LLMCompletion",
    "LLMConfig",
    "LLMProvider",
    "LLMProviderError",
    "LLMProviderUnavailableError",
    "default_config",
    "generate_completion",
    "get_llm_provider",
    "llm_available",
    "set_llm_provider",
]
