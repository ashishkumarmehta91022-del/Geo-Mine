"""OpenAI-compatible chat-completions provider (Step 10).

Works with any endpoint that implements POST {base_url}/chat/completions
(OpenAI, Azure OpenAI gateways, Ollama, vLLM, LM Studio, ...). Business logic
never references a specific vendor — only this provider knows the wire format.

Security invariants:
- The API key is read from configuration only, sent as a bearer header, and
  NEVER logged, returned, or embedded in error messages.
- Timeouts are mandatory; no unbounded requests.
- Non-JSON or malformed responses raise LLMProviderError — never silent text.
- User/evidence content is passed as message content only; it never enters
  system instructions (built by the prompt builder, not this provider).
"""

import json
import logging
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

from app.llm.base import LLMCompletion, LLMProvider, LLMProviderError, LLMProviderUnavailableError

logger = logging.getLogger(__name__)


class OpenAICompatibleLLMProvider(LLMProvider):
    """HTTP chat-completions client for OpenAI-compatible endpoints."""

    name = "openai-compatible"

    def __init__(self, *, model: str, api_key: str, base_url: str) -> None:
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def is_available(self) -> bool:
        return bool(self.model and self._base_url)

    # -- internals -----------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _endpoint(self) -> str:
        return f"{self._base_url}/chat/completions"

    def _request(self, payload: dict, timeout_seconds: float) -> dict:
        """One bounded HTTP call. Raises LLMProviderError without leaking secrets."""
        body = json.dumps(payload).encode("utf-8")
        req = urlrequest.Request(
            self._endpoint(), data=body, headers=self._headers(), method="POST"
        )
        try:
            with urlrequest.urlopen(req, timeout=timeout_seconds) as response:
                raw = response.read()
        except HTTPError as exc:
            # Sanitize: status + safe reason only (never headers/body that
            # could echo the Authorization header back).
            raise LLMProviderError(
                f"LLM endpoint returned HTTP {exc.code} ({exc.reason})."
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise LLMProviderError(f"Could not reach the LLM endpoint: {exc.__class__.__name__}.") from exc
        try:
            parsed = json.loads(raw.decode("utf-8", errors="replace"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise LLMProviderError("LLM endpoint returned a non-JSON response.") from exc
        if not isinstance(parsed, dict):
            raise LLMProviderError("LLM endpoint returned an unexpected JSON shape.")
        return parsed

    @staticmethod
    def _extract_text(payload: dict) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMProviderError("LLM response contains no choices.")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        text = message.get("content") if isinstance(message, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise LLMProviderError("LLM response message is empty or malformed.")
        return text

    # -- LLMProvider ----------------------------------------------------------

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        timeout_seconds: float,
        max_output_chars: int,
    ) -> LLMCompletion:
        if not self.is_available():
            raise LLMProviderUnavailableError("LLM provider is not configured (model/base URL missing).")

        prompt_chars = sum(len(m.get("content", "")) for m in messages)
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,          # deterministic-ish; grounding comes from evidence
            "max_tokens": max(256, min(max_output_chars, 2000)),
            "stream": False,
        }
        parsed = self._request(payload, timeout_seconds)
        text = self._extract_text(parsed)
        model_used = parsed.get("model") if isinstance(parsed.get("model"), str) else self.model
        return LLMCompletion(
            text=text[:max_output_chars],
            provider=self.name,
            model=model_used,
            prompt_chars=prompt_chars,
            completion_chars=len(text[:max_output_chars]),
        )
