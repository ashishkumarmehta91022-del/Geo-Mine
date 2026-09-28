"""AI Query configuration — bounded, explicit, env-overridable.

Bounds (question length, evidence window, context size, answer size) live
here so every guardrail is documented and testable in one place. Values may
be overridden via AI_QUERY_* environment variables.
"""

from dataclasses import dataclass

from app.config import settings

# Hard caps for the AI Query pipeline (Step 10 contract).
MAX_QUESTION_LENGTH = 500
MAX_EVIDENCE_UNITS = 12          # evidence window handed to the LLM
MAX_CONTEXT_CHARS = 12_000       # evidence block budget in the prompt
MAX_ANSWER_CHARS = 4_000         # completion truncation bound


@dataclass(frozen=True)
class LLMConfig:
    """Provider identity + guardrails for one AI Query run."""

    provider: str          # "" ⇒ unavailable; e.g. "openai-compatible"
    model: str             # resolved model name ("" until a provider resolves it)
    api_key: str           # environment only — never logged, never returned
    base_url: str          # for openai-compatible endpoints
    timeout_seconds: float
    max_question_chars: int = MAX_QUESTION_LENGTH
    max_evidence_units: int = MAX_EVIDENCE_UNITS
    max_context_chars: int = MAX_CONTEXT_CHARS
    max_answer_chars: int = MAX_ANSWER_CHARS

    @classmethod
    def from_settings(cls) -> "LLMConfig":
        """Build from env-driven settings (keys stay out of code)."""
        return cls(
            provider=settings.llm_provider.strip().lower(),
            model=settings.llm_model.strip(),
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url.strip().rstrip("/"),
            timeout_seconds=max(1.0, float(settings.llm_timeout_seconds)),
        )


def default_config() -> LLMConfig:
    return LLMConfig.from_settings()
