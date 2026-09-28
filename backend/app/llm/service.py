"""LLM service: provider access, availability, bounded completion calls.

Mirrors app/embeddings/service.py: one process-wide provider (lazy), test
injection via set_llm_provider, and a single guarded entry point that never
leaks secrets and never fabricates content. Business logic only ever calls
llm_available() / generate_completion() — never a concrete vendor class.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError

from app.llm.base import (
    LLMCompletion,
    LLMProvider,
    LLMProviderError,
    LLMProviderUnavailableError,
)
from app.llm.config import LLMConfig, default_config
from app.llm.openai_provider import OpenAICompatibleLLMProvider

logger = logging.getLogger(__name__)

_default_provider: LLMProvider | None = None


def get_llm_provider(config: LLMConfig | None = None) -> LLMProvider:
    """Return the process-wide provider (lazy singleton from settings)."""
    global _default_provider
    if _default_provider is None:
        cfg = config or default_config()
        if cfg.provider == "openai-compatible":
            _default_provider = OpenAICompatibleLLMProvider(
                model=cfg.model, api_key=cfg.api_key, base_url=cfg.base_url
            )
        elif cfg.provider == "mock":
            # Only reachable when explicitly configured via LLM_PROVIDER=mock.
            from app.llm.mock_provider import MockLLMProvider

            _default_provider = MockLLMProvider()
        # Unknown/empty provider name ⇒ stays None ⇒ unavailable (honest).
    return _default_provider  # may be None


def set_llm_provider(provider: LLMProvider | None) -> None:
    """Replace the default provider (tests inject fakes/mock here)."""
    global _default_provider
    _default_provider = provider


def llm_available(config: LLMConfig | None = None) -> bool:
    """Whether a usable LLM provider exists right now (no side effects)."""
    provider = get_llm_provider(config)
    try:
        return bool(provider is not None and provider.is_available())
    except Exception:  # noqa: BLE001 — availability probing never raises
        return False


def generate_completion(
    messages: list[dict[str, str]], config: LLMConfig
) -> tuple[LLMCompletion | None, str | None, float]:
    """One bounded, timed completion call.

    Returns (completion, error, elapsed_seconds) — exactly one of
    completion/error is None. Errors are honest and secret-free:
      - "unavailable: …" no provider configured
      - "failed: …" provider error or timeout
    Never fabricates an answer.
    """
    provider = get_llm_provider(config)
    if provider is None or not provider.is_available():
        return None, "unavailable: no usable LLM provider is configured", 0.0

    start = time.monotonic()
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(
            provider.generate,
            messages,
            timeout_seconds=config.timeout_seconds,
            max_output_chars=config.max_answer_chars,
        )
        completion = future.result(timeout=config.timeout_seconds)
        return completion, None, time.monotonic() - start
    except FutureTimeoutError:
        logger.warning("LLM call exceeded %.1fs timeout", config.timeout_seconds)
        return None, f"failed: LLM call timed out after {config.timeout_seconds:g}s", time.monotonic() - start
    except LLMProviderUnavailableError as exc:
        return None, f"unavailable: {exc}", time.monotonic() - start
    except LLMProviderError as exc:
        return None, f"failed: {exc}", time.monotonic() - start
    except Exception as exc:  # noqa: BLE001 — honest, secret-free catch-all
        logger.warning("LLM call failed: %s", exc.__class__.__name__)
        return None, f"failed: {exc.__class__.__name__}", time.monotonic() - start
    finally:
        executor.shutdown(wait=False)
