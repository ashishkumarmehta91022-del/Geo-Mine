"""AI Query orchestration (Step 10): retrieval-first, provenance-grounded.

Pipeline (fixed order, no shortcuts):
  1. validate the question (bounded, non-empty)
  2. retrieval-first over the Step 8/9 knowledge index (the LLM never
     searches anything and is never called without evidence)
  3. bounded evidence with full provenance (evidence_id = list position)
  4. deterministic conflict detection (no winner selection, ever)
  5. structured prompt: fixed system rules + delimited question/evidence
  6. one bounded LLM completion via the pluggable provider
  7. strict JSON contract validation (answer/evidence_ids/conflict_detected/
     insufficient_evidence/limitations); citations filtered to real ids

Honesty guarantees:
- No evidence ⇒ `insufficient_evidence` result; the LLM is never invoked.
- LLM unavailable/failed ⇒ `llm_unavailable` result (HTTP 503 at the route);
  never a fabricated answer.
- Retrieved documents are untrusted data and cannot override system rules.
"""

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.evidence import (
    ConflictGroup,
    Evidence,
    attach_retrieval_scores,
    build_evidence,
    detect_conflicts,
)
from app.constants import RetrievalMode
from app.exceptions import AppError, DatabaseUnavailableError
from app.knowledge.query_parser import SearchQuery, parse_search_query
from app.llm import LLMConfig, default_config
from app.llm.prompts import build_messages, conflict_line, evidence_line
from app.llm.service import generate_completion, llm_available
from app.models import Document, DocumentPage, ExtractedRecord

logger = logging.getLogger(__name__)

# Evidence block budget (chars) inside the user message.
MAX_EVIDENCE_BLOCK_CHARS = 8000
# Strict JSON contract keys (exactly these — no extras, none missing).
RESPONSE_KEYS = {
    "answer",
    "evidence_ids",
    "conflict_detected",
    "insufficient_evidence",
    "limitations",
}


def question_error(question: str) -> AppError | None:
    """Validate a raw question. Returns the error to raise, or None."""
    if question is None or not question.strip():
        return AppError(
            status_code=422, code="empty_question", message="A non-empty question is required."
        )
    if len(question) > 500:
        return AppError(
            status_code=422,
            code="question_too_long",
            message=f"Question exceeds the 500-character limit ({len(question)}).",
        )
    return None


def _load_context(
    db: Session, rows: list
) -> tuple[dict[int, str], dict[int, int], dict[int, tuple[str | None, str | None]]]:
    """Load filename/page_number/record values for evidence construction.

    Values come from the authoritative tables — never re-derived, never
    modified here (value_raw passes through verbatim).
    """
    document_ids = {row.document_id for row in rows}
    page_ids = {row.page_id for row in rows if row.page_id is not None}
    record_ids = {row.record_id for row in rows if row.record_id is not None}

    filenames: dict[int, str] = {}
    if document_ids:
        filenames = dict(
            db.execute(
                select(Document.id, Document.filename).where(Document.id.in_(document_ids))
            ).all()
        )
    page_numbers: dict[int, int] = {}
    if page_ids:
        page_numbers = dict(
            db.execute(
                select(DocumentPage.id, DocumentPage.page_number).where(DocumentPage.id.in_(page_ids))
            ).all()
        )
    record_values: dict[int, tuple[str | None, str | None]] = {}
    if record_ids:
        record_values = {
            rid: (value_raw, normalized_value)
            for rid, value_raw, normalized_value in db.execute(
                select(
                    ExtractedRecord.id,
                    ExtractedRecord.value_raw,
                    ExtractedRecord.normalized_value,
                ).where(ExtractedRecord.id.in_(record_ids))
            ).all()
        }
    return filenames, page_numbers, record_values


def _build_evidence_block(evidence: list[Evidence]) -> str:
    """Deterministic numbered evidence block (bounded chars, single lines)."""
    lines: list[str] = []
    total = 0
    for item in evidence:
        line = evidence_line(item.evidence_id, item.snippet or "", item.prompt_meta())
        if total + len(line) > MAX_EVIDENCE_BLOCK_CHARS and lines:
            break
        lines.append(line)
        total += len(line) + 1
    return "\n".join(lines)


def _conflict_notices(conflicts: list[ConflictGroup]) -> list[str]:
    return [
        conflict_line(c.entity, c.metric, c.reporting_period, c.values, c.evidence_ids)
        for c in conflicts
    ]


def parse_llm_response(raw: str, valid_ids: set[int]) -> dict[str, Any]:
    """Validate the strict JSON contract. Raises ValueError on any violation.

    Citations are filtered to ids that exist in this run's evidence: a model
    citing unknown ids loses those citations (claims lose support rather than
    gaining fake backing).
    """
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError("LLM response is not valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("LLM response is not a JSON object.")
    missing = RESPONSE_KEYS - set(parsed)
    if missing:
        raise ValueError(f"LLM response missing required keys: {sorted(missing)}.")
    extra = set(parsed) - RESPONSE_KEYS
    if extra:
        raise ValueError(f"LLM response contains unexpected keys: {sorted(extra)}.")

    answer = parsed["answer"]
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("LLM 'answer' must be a non-empty string.")
    raw_ids = parsed["evidence_ids"]
    if not isinstance(raw_ids, list) or not all(
        isinstance(i, int) and not isinstance(i, bool) for i in raw_ids
    ):
        raise ValueError("LLM 'evidence_ids' must be a list of integers.")
    conflict_flag = parsed["conflict_detected"]
    insufficient_flag = parsed["insufficient_evidence"]
    if not isinstance(conflict_flag, bool) or not isinstance(insufficient_flag, bool):
        raise ValueError("LLM conflict/insufficient flags must be booleans.")
    limitations = parsed["limitations"]
    if not isinstance(limitations, str):
        raise ValueError("LLM 'limitations' must be a string.")

    return {
        "answer": answer.strip(),
        "evidence_ids": [i for i in raw_ids if i in valid_ids],
        "conflict_detected": conflict_flag,
        "insufficient_evidence": insufficient_flag,
        "limitations": limitations.strip(),
        "invalid_citations_dropped": sorted(set(raw_ids) - valid_ids),
    }


def _no_evidence_result(question: str, mode: str, retrieval_total: int) -> dict[str, Any]:
    """Honest no-evidence outcome — the LLM is never invoked in this state."""
    return {
        "status": "insufficient_evidence",
        "question": question,
        "retrieval_mode": mode,
        "retrieval_total": retrieval_total,
        "evidence": [],
        "evidence_ids": [],
        "answer": (
            "Insufficient evidence: the available project documents do not "
            "contain enough supporting information to answer this question. "
            "No answer is generated without evidence."
        ),
        "conflict_detected": False,
        "conflicts": [],
        "insufficient_evidence": True,
        "provider": None,
        "model": None,
        "limitations": "No relevant evidence was retrieved from the indexed project documents.",
    }


def _unavailable_result(
    question: str,
    mode: str,
    evidence: list[Evidence],
    conflicts: list[ConflictGroup],
    reason: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    latency_ms: int | None = None,
) -> dict[str, Any]:
    """LLM unavailable/failed/malformed — evidence still returned honestly."""
    result: dict[str, Any] = {
        "status": "llm_unavailable" if provider is None else "llm_error",
        "question": question,
        "retrieval_mode": mode,
        "evidence": [item.to_payload() for item in evidence],
        "evidence_ids": [item.evidence_id for item in evidence],
        "answer": None,
        "conflict_detected": bool(conflicts),
        "conflicts": [c.to_payload() for c in conflicts],
        "insufficient_evidence": False,
        "provider": provider,
        "model": model,
        "error": reason,
    }
    if latency_ms is not None:
        result["latency_ms"] = latency_ms
    return result


def _query_vector(text: str) -> tuple[list[float] | None, str | None]:
    """Embed the question for hybrid retrieval (Step 9 embedding service)."""
    from app.embeddings import default_config as default_embedding_config
    from app.embeddings.service import timed_embed

    result, error, _elapsed = timed_embed([text], default_embedding_config())
    if error or result is None or not result.vectors:
        return None, error or "embedding produced no vector"
    return result.vectors[0], None


def run_ai_query(
    db: Session,
    question: str,
    *,
    mode: str = RetrievalMode.HYBRID,
    limit: int | None = None,
    config: LLMConfig | None = None,
) -> dict[str, Any]:
    """Full retrieval-grounded AI query pipeline (see module docstring)."""
    cfg = config or default_config()

    error = question_error(question)
    if error is not None:
        raise error

    # Semantic-only AI queries are rejected: they cannot carry the lexical
    # complement of hybrid and silently exclude un-embedded evidence.
    if mode == RetrievalMode.SEMANTIC:
        raise AppError(
            status_code=422,
            code="unsupported_ai_mode",
            message="AI query requires grounded retrieval; use mode=hybrid (default) or lexical.",
        )
    retrieval_mode = mode if mode in RetrievalMode.values() else RetrievalMode.HYBRID
    evidence_window = limit if limit is not None else cfg.max_evidence_units

    # --- 1. retrieval-first: always through the Step 8/9 index -------------
    from app.services import knowledge_service

    query: SearchQuery = parse_search_query(q=question, limit=evidence_window, offset=0)
    try:
        if retrieval_mode == RetrievalMode.HYBRID:
            vector, embed_error = _query_vector(query.text)
            if vector is not None:
                data = knowledge_service.search_hybrid(db, query, vector)
                retrieval_note = None
            else:
                # Honest degradation: lexical evidence only, reason attached.
                data = knowledge_service.search(db, query)
                retrieval_note = f"semantic retrieval unavailable ({embed_error}); lexical evidence only"
        else:
            data = knowledge_service.search(db, query)
            retrieval_note = None
    except DatabaseUnavailableError:
        raise
    except OperationalError as exc:
        raise DatabaseUnavailableError from exc

    rows: list = data.get("results", [])
    row_ids: list[int] = [row.id for row in rows]
    retrieval_total = int(data.get("total", 0))

    # --- 2. evidence construction (bounded, provenance-complete) ----------
    try:
        filenames, page_numbers, record_values = _load_context(db, rows)
    except OperationalError as exc:
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        raise AppError(
            status_code=500, code="database_error", message="Could not load evidence context."
        ) from exc

    evidence = build_evidence(
        rows,
        filenames=filenames,
        page_numbers=page_numbers,
        record_values=record_values,
        max_units=evidence_window,
    )

    # --- 3. no useful evidence ⇒ honest insufficiency, LLM never called ---
    if not evidence or not any(item.snippet for item in evidence):
        return _no_evidence_result(question, retrieval_mode, retrieval_total)

    conflicts = detect_conflicts(evidence)
    evidence = attach_retrieval_scores(evidence, row_ids, data.get("scores") or {})

    # --- 4. LLM gate: explicit unavailability, never fabrication ----------
    if not llm_available(cfg):
        return _unavailable_result(
            question,
            retrieval_mode,
            evidence,
            conflicts,
            "unavailable: no usable LLM provider is configured",
        )

    messages = build_messages(
        question,
        _build_evidence_block(evidence),
        cfg,
        conflict_lines=_conflict_notices(conflicts),
    )
    completion, llm_error, elapsed = generate_completion(messages, cfg)
    if completion is None:
        return _unavailable_result(
            question, retrieval_mode, evidence, conflicts, llm_error or "failed: unknown LLM error"
        )

    # --- 5. strict response-contract validation ---------------------------
    valid_ids = {item.evidence_id for item in evidence}
    try:
        parsed = parse_llm_response(completion.text, valid_ids)
    except ValueError as exc:
        return _unavailable_result(
            question,
            retrieval_mode,
            evidence,
            conflicts,
            f"malformed provider response: {exc}",
            provider=completion.provider,
            model=completion.model,
            latency_ms=int(elapsed * 1000),
        )

    # --- 6. success: answer + citations + provenance ----------------------
    result: dict[str, Any] = {
        "status": "ok",
        "question": question,
        "retrieval_mode": retrieval_mode,
        "retrieval_total": retrieval_total,
        "evidence": [item.to_payload() for item in evidence],
        "evidence_ids": parsed["evidence_ids"],
        "answer": parsed["answer"],
        # Deterministic application-level detection wins over the model's
        # self-report: arithmetic conflicts always surface, never hidden.
        "conflict_detected": bool(conflicts) or parsed["conflict_detected"],
        "conflicts": [c.to_payload() for c in conflicts],
        "insufficient_evidence": False,
        "limitations": parsed["limitations"] or None,
        "provider": completion.provider,
        "model": completion.model,
        "latency_ms": int(elapsed * 1000),
        "invalid_citations_dropped": parsed["invalid_citations_dropped"],
    }
    if retrieval_note:
        result["retrieval_note"] = retrieval_note
    return result


def audit_metadata(result: dict[str, Any]) -> dict[str, Any]:
    """Safe audit payload: metadata only — never question text, never answers,
    never API keys, never document content."""
    return {
        "status": result.get("status"),
        "retrieval_mode": result.get("retrieval_mode"),
        "evidence_units": len(result.get("evidence", [])),
        "conflict_detected": result.get("conflict_detected", False),
        "insufficient_evidence": result.get("insufficient_evidence", False),
        "provider": result.get("provider"),
        "model": result.get("model"),
        "latency_ms": result.get("latency_ms"),
    }
