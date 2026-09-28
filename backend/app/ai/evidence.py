"""Evidence construction + deterministic conflict detection (Step 10).

Evidence objects are the ONLY content the LLM may ground on. Every piece
keeps full Step 8 provenance and a deterministic evidence_id (index into the
ordered evidence list — stable across identical requests). `value_raw` is
passed through verbatim; OCR text is never corrected.

Conflict detection is pure arithmetic on (entity, metric, reporting_period)
keys with distinct RAW values: deterministic, no LLM involvement, no winner
selection — both sides stay in the evidence list and are reported.
"""

from dataclasses import dataclass
from typing import Any

from app.models import KnowledgeIndex


@dataclass(frozen=True)
class Evidence:
    """One retrieved unit promoted to LLM evidence (provenance preserved)."""

    evidence_id: int                 # 1-based, deterministic (list position)
    unit_type: str
    document_id: int
    document_name: str | None = None
    page_id: int | None = None
    page_number: int | None = None
    record_id: int | None = None
    validation_id: int | None = None
    source_reference: str | None = None
    extraction_method: str | None = None
    validation_status: str | None = None
    ocr_confidence: float | None = None
    entity: str | None = None
    metric: str | None = None
    unit: str | None = None
    reporting_period: str | None = None
    value_raw: str | None = None     # verbatim from the source — never modified
    normalized_value: str | None = None
    snippet: str | None = None
    # Retrieval metrics (relevance, never trust).
    lexical_score: float | None = None
    semantic_similarity: float | None = None
    relevance: float | None = None

    def to_payload(self) -> dict[str, Any]:
        """Frontend/API representation — full provenance, no fabricated fields."""
        return {
            "evidence_id": self.evidence_id,
            "unit_type": self.unit_type,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "page_id": self.page_id,
            "page_number": self.page_number,
            "record_id": self.record_id,
            "validation_id": self.validation_id,
            "source_reference": self.source_reference,
            "extraction_method": self.extraction_method,
            "validation_status": self.validation_status,
            "ocr_confidence": self.ocr_confidence,
            "entity": self.entity,
            "metric": self.metric,
            "unit": self.unit,
            "reporting_period": self.reporting_period,
            "value_raw": self.value_raw,
            "normalized_value": self.normalized_value,
            "snippet": self.snippet,
            "lexical_score": self.lexical_score,
            "semantic_similarity": self.semantic_similarity,
            "relevance": self.relevance,
        }

    def prompt_meta(self) -> str:
        """Compact deterministic metadata string for the prompt line."""
        bits: list[str] = [f"doc {self.document_id}"]
        if self.document_name:
            bits.append(str(self.document_name))
        if self.page_number is not None:
            bits.append(f"page {self.page_number}")
        if self.entity:
            bits.append(f"entity {self.entity}")
        if self.metric:
            bits.append(f"metric {self.metric}")
        if self.value_raw is not None:
            value_bits = [f"value {self.value_raw}"]
            if self.unit:
                value_bits.append(self.unit)
            bits.append(" ".join(value_bits))
        elif self.normalized_value:
            bits.append(f"value {self.normalized_value}")
        if self.reporting_period:
            bits.append(f"period {self.reporting_period}")
        if self.extraction_method:
            bits.append(f"extracted via {self.extraction_method}")
        if self.validation_status:
            bits.append(f"validation {self.validation_status}")
        if self.ocr_confidence is not None:
            bits.append(f"OCR {round(self.ocr_confidence, 2)}")
        return "; ".join(bits)


@dataclass(frozen=True)
class ConflictGroup:
    """One (entity, metric, period) with disagreeing raw values.

    No winner is ever selected: every side stays in `evidence_ids` and the
    LLM is instructed to report the disagreement, not resolve it.
    """

    entity: str | None
    metric: str | None
    reporting_period: str | None
    values: tuple[str, ...]          # distinct raw values, first-seen order
    evidence_ids: tuple[int, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "entity": self.entity,
            "metric": self.metric,
            "reporting_period": self.reporting_period,
            "values": list(self.values),
            "evidence_ids": list(self.evidence_ids),
        }


def build_evidence(
    rows: list,
    *,
    filenames: dict[int, str],
    page_numbers: dict[int, int],
    record_values: dict[int, tuple[str | None, str | None]],
    max_units: int,
) -> list[Evidence]:
    """Turn ordered retrieval rows into bounded, deterministic evidence.

    - rows come from the retrieval service already ranked; order is preserved
      (first N win — no re-ranking here).
    - record_values maps record_id → (value_raw, normalized_value) pulled from
      the authoritative extracted_records table (source of truth untouched).
    """
    evidence: list[Evidence] = []
    for row in rows[: max_units]:
        value_raw, normalized_value = (None, None)
        if row.unit_type == "record" and row.record_id is not None:
            value_raw, normalized_value = record_values.get(row.record_id, (None, None))
        snippet = _snippet_for(row)
        evidence.append(
            Evidence(
                evidence_id=len(evidence) + 1,
                unit_type=row.unit_type,
                document_id=row.document_id,
                document_name=filenames.get(row.document_id),
                page_id=row.page_id,
                page_number=page_numbers.get(row.page_id) if row.page_id is not None else None,
                record_id=row.record_id,
                validation_id=row.validation_id,
                source_reference=row.source_reference,
                extraction_method=row.extraction_method,
                validation_status=row.validation_status,
                ocr_confidence=float(row.ocr_confidence) if row.ocr_confidence is not None else None,
                entity=row.entity,
                metric=row.metric,
                unit=row.unit,
                reporting_period=row.reporting_period,
                value_raw=value_raw,
                normalized_value=normalized_value,
                snippet=snippet,
                lexical_score=None,
                semantic_similarity=None,
                relevance=None,
            )
        )
    return evidence


def _snippet_for(row: KnowledgeIndex) -> str | None:
    """Deterministic snippet: title + leading content (no OCR 'correction')."""
    parts = []
    if row.title:
        parts.append(row.title)
    if row.content:
        parts.append(row.content)
    text = " — ".join(parts).strip()
    if not text:
        return None
    return " ".join(text.split())[:400]


def detect_conflicts(evidence: list[Evidence]) -> list[ConflictGroup]:
    """Deterministic conflict detection over record evidence.

    Grouping key: (entity, metric, reporting_period) — only RECORD units with
    a non-empty raw value participate. Distinct values within a group ⇒ a
    conflict covering every member. No winner, no merging, no correction.
    """
    groups: dict[tuple[str | None, str | None, str | None], dict[str, list[int]]] = {}
    for item in evidence:
        if item.unit_type != "record" or not item.value_raw:
            continue
        key = (item.entity, item.metric, item.reporting_period)
        groups.setdefault(key, {}).setdefault(item.value_raw, []).append(item.evidence_id)

    conflicts: list[ConflictGroup] = []
    for (entity, metric, period) in sorted(
        groups, key=lambda k: (k[0] or "", k[1] or "", k[2] or "")
    ):
        by_value = groups[(entity, metric, period)]
        if len(by_value) < 2:
            continue
        ordered_values = sorted(by_value, key=lambda v: by_value[v][0])
        conflicts.append(
            ConflictGroup(
                entity=entity,
                metric=metric,
                reporting_period=period,
                values=tuple(ordered_values),
                evidence_ids=tuple(
                    eid for value in ordered_values for eid in by_value[value]
                ),
            )
        )
    return conflicts


def attach_retrieval_scores(
    evidence: list[Evidence],
    row_ids: list[int],
    scores: dict[int, dict[str, Any]],
) -> list[Evidence]:
    """Copy evidence with lexical/semantic/combined scores attached.

    `scores` comes from the hybrid contract: {knowledge_index.row_id: {
    lexical, semantic, combined, ...}}. `row_ids` is the ordered retrieval-row
    id list that produced the evidence (evidence_id i ⇒ row_ids[i-1]).
    Evidence stays immutable; a new list is returned.
    """
    if not scores or not row_ids:
        return evidence
    enriched: list[Evidence] = []
    for item in evidence:
        row_id = row_ids[item.evidence_id - 1] if item.evidence_id <= len(row_ids) else None
        entry = scores.get(row_id) or {} if row_id is not None else {}
        enriched.append(
            Evidence(
                **{
                    **item.__dict__,
                    "lexical_score": entry.get("lexical"),
                    "semantic_similarity": entry.get("semantic"),
                    "relevance": entry.get("combined"),
                }
            )
        )
    return enriched
