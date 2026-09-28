"""Deterministic mock LLM provider — TESTS/DEMO ONLY, explicitly labeled.

The mock always returns a response in the Step 10 strict JSON contract, with
the "[MOCK LLM]" marker inside both `answer` and `limitations` so mock output
can never be mistaken for a real production answer. It is selected only by
tests (via set_llm_provider) or by explicitly configuring LLM_PROVIDER=mock.

Determinism: given the same evidence block, the answer is byte-identical —
no randomness anywhere.
"""

import json

from app.llm.base import LLMCompletion, LLMProvider


class MockLLMProvider(LLMProvider):
    """Deterministic, contract-valid, clearly-labeled stand-in."""

    name = "mock"
    model = "mock-deterministic-v1"

    def __init__(self, *, available: bool = True, fail_with: Exception | None = None) -> None:
        self._available = available
        self._fail_with = fail_with
        self.calls: list[list[dict[str, str]]] = []  # observability for assertions

    def is_available(self) -> bool:
        return self._available

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        timeout_seconds: float,
        max_output_chars: int,
    ) -> LLMCompletion:
        self.calls.append([dict(m) for m in messages])
        if self._fail_with is not None:
            raise self._fail_with

        # Ground the answer only on what the prompt actually contained.
        user_content = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
        conflict_seen = "CONFLICT:" in user_content
        cited_ids = sorted({int(tok[1:]) for tok in user_content.split() if tok.startswith("[") and tok[1:].rstrip("]").isdigit()})

        payload = {
            "answer": (
                "[MOCK LLM] Based only on the supplied evidence "
                f"({len(cited_ids)} items cited). "
                + ("Conflicts were flagged in the evidence and are reported, not resolved. "
                   if conflict_seen
                   else "")
                + "This is a deterministic mock provider output, not verified data."
            ),
            "evidence_ids": cited_ids,
            "conflict_detected": conflict_seen,
            "insufficient_evidence": False,
            "limitations": "[MOCK LLM] Mock provider output — not a real model, not verified data.",
        }
        text = json.dumps(payload)[:max_output_chars]
        return LLMCompletion(
            text=text,
            provider=self.name,
            model=self.model,
            prompt_chars=sum(len(m.get("content", "")) for m in messages),
            completion_chars=len(text),
        )
