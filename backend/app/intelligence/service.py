"""Document intelligence orchestration (Step 13).

Compose corpus → keywords/phrases → topics → word cloud → relationships →
deterministic summary, all bounded and deterministic, with an optional AI
prose summary that never blocks the deterministic result.
"""

from typing import Any

from sqlalchemy.orm import Session

from app.intelligence.corpus import build_corpus
from app.intelligence.keywords import extract_keywords
from app.intelligence.models import DocumentIntelligenceResult
from app.intelligence.summary import build_ai_summary, build_deterministic_summary
from app.intelligence.topics import identify_topics, topic_document_matches
from app.intelligence.wordcloud import generate_word_cloud

LIMITATIONS = [
    "Derived intelligence is rebuilt on demand from the existing knowledge "
    "index and never stored as a second source of truth.",
    "Topic labels are derived from corpus terms — they are NOT official "
    "CMPDI/CIL topic definitions.",
    "Bare numbers are excluded from keywords/topics (out-of-context numbers "
    "are meaningless and could fabricate importance).",
]


def analyze_document(
    db: Session,
    document_id: int,
    *,
    include_ai_summary: bool = False,
    config=None,
) -> dict[str, Any]:
    """Full intelligence payload for one document (deterministic + optional AI)."""
    corpus = build_corpus(db, [document_id])
    keyword_data = extract_keywords(corpus)
    topic_data = identify_topics(corpus)
    topics = topic_data["topics"]
    matches = topic_document_matches(
        corpus, topics, topic_data["term_units"], topic_data["term_frequency"]
    )
    cloud = generate_word_cloud(corpus)
    summary = build_deterministic_summary(db, document_id, corpus, topics)
    ai_summary = None
    if include_ai_summary:
        ai_summary = build_ai_summary(db, document_id, corpus, config=config)
    result = DocumentIntelligenceResult(
        scope="document",
        document_ids=[document_id],
        keywords=keyword_data["keywords"],
        topics=topics,
        word_cloud=cloud,
        topic_document_matches=matches,
        summaries=[summary],
        corpus_stats=corpus.stats,
        ai_summary=ai_summary,
        limitations=list(LIMITATIONS),
    )
    payload = result.to_payload()
    payload["summary"] = summary.to_payload()
    return payload


def analyze_corpus(
    db: Session,
    document_ids: list[int] | None = None,
) -> dict[str, Any]:
    """Corpus-wide intelligence: keywords, topics, cloud, relationships."""
    corpus = build_corpus(db, document_ids)
    keyword_data = extract_keywords(corpus)
    topic_data = identify_topics(corpus)
    topics = topic_data["topics"]
    matches = topic_document_matches(
        corpus, topics, topic_data["term_units"], topic_data["term_frequency"]
    )
    cloud = generate_word_cloud(corpus)
    result = DocumentIntelligenceResult(
        scope="corpus",
        document_ids=corpus.document_ids,
        keywords=keyword_data["keywords"],
        topics=topics,
        word_cloud=cloud,
        topic_document_matches=matches,
        corpus_stats=corpus.stats,
        limitations=list(LIMITATIONS),
    )
    return result.to_payload()


def audit_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Safe audit metadata — counts only, never document contents."""
    return {
        "scope": payload.get("scope"),
        "document_count": len(payload.get("document_ids", []) or []),
        "keyword_count": len(payload.get("keywords", []) or []),
        "topic_count": len(payload.get("topics", []) or []),
        "cloud_term_count": len(payload.get("word_cloud", []) or []),
        "match_count": len(payload.get("topic_document_matches", []) or []),
        "unit_count": (payload.get("corpus_stats") or {}).get("unit_count"),
        "ai_summary_state": (payload.get("ai_summary") or {}).get("state")
        if payload.get("ai_summary") is not None
        else None,
    }
