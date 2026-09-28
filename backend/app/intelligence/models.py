"""Typed document-intelligence models (Step 13).

All intelligence objects are DERIVED, rebuildable views over the existing
extraction pipeline and knowledge index — never a second source of truth.
Every object keeps provenance (document/page/unit references) so each topic,
keyword and summary statement is traceable to extracted content.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class TermKind(StrEnum):
    TERM = "term"
    PHRASE = "phrase"


@dataclass(frozen=True)
class SourceRef:
    """Provenance for one contributing corpus unit."""

    document_id: int
    page_id: int | None = None
    page_number: int | None = None
    unit_type: str = "page"          # page | record
    source_reference: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "page_id": self.page_id,
            "page_number": self.page_number,
            "unit_type": self.unit_type,
            "source_reference": self.source_reference,
        }


@dataclass(frozen=True)
class CorpusUnit:
    """One bounded text unit feeding the intelligence corpus."""

    unit_id: int                     # deterministic index within the corpus
    document_id: int
    page_id: int | None
    page_number: int | None
    unit_type: str                   # page | record
    source_reference: str | None
    tokens: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Keyword:
    """One ranked keyword or phrase with full provenance."""

    term: str                        # normalized (comparison form)
    display_term: str                # preserved display form
    kind: str                        # TermKind.TERM | TermKind.PHRASE
    frequency: int
    document_frequency: int
    score: float
    score_reason: str                # explained ranking signal
    sources: list[SourceRef] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "term": self.term,
            "display_term": self.display_term,
            "kind": self.kind,
            "frequency": self.frequency,
            "document_frequency": self.document_frequency,
            "score": round(self.score, 4),
            "score_reason": self.score_reason,
            "sources": [source.to_payload() for source in self.sources],
        }


@dataclass(frozen=True)
class WordCloudTerm:
    """One word-cloud data point (frontend renders it; no backend image)."""

    term: str
    display_term: str
    weight: float                    # 0..1 normalized score
    frequency: int
    document_frequency: int
    kind: str
    sources: list[SourceRef] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "term": self.term,
            "display_term": self.display_term,
            "weight": round(self.weight, 4),
            "frequency": self.frequency,
            "document_frequency": self.document_frequency,
            "kind": self.kind,
            "sources": [source.to_payload() for source in self.sources],
        }


@dataclass(frozen=True)
class Topic:
    """One deterministically derived topic (label comes from its terms)."""

    topic_id: str                    # deterministic: t1, t2, … by rank
    label: str                       # derived from underlying terms only
    score: float
    representative_terms: list[str] = field(default_factory=list)
    document_ids: list[int] = field(default_factory=list)
    sources: list[SourceRef] = field(default_factory=list)
    method: str = "keyword-cluster"  # documented derivation method

    def to_payload(self) -> dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "label": self.label,
            "score": round(self.score, 4),
            "representative_terms": list(self.representative_terms),
            "document_ids": list(self.document_ids),
            "sources": [source.to_payload() for source in self.sources],
            "method": self.method,
        }


@dataclass(frozen=True)
class TopicDocumentMatch:
    """Topic ↔ document relationship (score + supporting terms)."""

    topic_id: str
    topic_label: str
    document_id: int
    score: float
    supporting_terms: list[str] = field(default_factory=list)
    sources: list[SourceRef] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "topic_label": self.topic_label,
            "document_id": self.document_id,
            "score": round(self.score, 4),
            "supporting_terms": list(self.supporting_terms),
            "sources": [source.to_payload() for source in self.sources],
        }


@dataclass(frozen=True)
class DocumentSummary:
    """Deterministic document summary (no LLM required)."""

    document_id: int
    document_name: str
    document_type: str
    page_count: int
    extraction_status: str | None
    validation_status: str | None
    record_count: int
    warning_error_review_count: int
    pending_validation_count: int
    conflict_count: int
    summary_text: str
    key_terms: list[Keyword] = field(default_factory=list)
    top_topics: list[Topic] = field(default_factory=list)
    key_metrics: list[dict[str, Any]] = field(default_factory=list)
    corpus_truncated: bool = False
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_payload(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "document_name": self.document_name,
            "document_type": self.document_type,
            "page_count": self.page_count,
            "extraction_status": self.extraction_status,
            "validation_status": self.validation_status,
            "record_count": self.record_count,
            "warning_error_review_count": self.warning_error_review_count,
            "pending_validation_count": self.pending_validation_count,
            "conflict_count": self.conflict_count,
            "summary_text": self.summary_text,
            "key_terms": [term.to_payload() for term in self.key_terms],
            "top_topics": [topic.to_payload() for topic in self.top_topics],
            "key_metrics": [dict(item) for item in self.key_metrics],
            "corpus_truncated": self.corpus_truncated,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class DocumentIntelligenceResult:
    """Complete intelligence payload for one document or a corpus."""

    scope: str                       # document | corpus
    document_ids: list[int] = field(default_factory=list)
    keywords: list[Keyword] = field(default_factory=list)
    topics: list[Topic] = field(default_factory=list)
    word_cloud: list[WordCloudTerm] = field(default_factory=list)
    topic_document_matches: list[TopicDocumentMatch] = field(default_factory=list)
    summaries: list[DocumentSummary] = field(default_factory=list)
    corpus_stats: dict[str, Any] = field(default_factory=dict)
    ai_summary: dict[str, Any] | None = None
    limitations: list[str] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "document_ids": list(self.document_ids),
            "keywords": [keyword.to_payload() for keyword in self.keywords],
            "topics": [topic.to_payload() for topic in self.topics],
            "word_cloud": [term.to_payload() for term in self.word_cloud],
            "topic_document_matches": [
                match.to_payload() for match in self.topic_document_matches
            ],
            "summaries": [summary.to_payload() for summary in self.summaries],
            "corpus_stats": dict(self.corpus_stats),
            "ai_summary": self.ai_summary,
            "limitations": list(self.limitations),
        }
