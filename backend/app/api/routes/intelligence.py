"""Document & topic intelligence routes (Step 13).

All endpoints serve DETERMINISTIC derived intelligence from the existing
knowledge index; the AI prose summary is opt-in and never blocks anything.
Provenance is included wherever terms/topics reference corpus units.

Error contract (honest):
- 404 document_not_found / no_indexed_content
- 503 database_unavailable
- AI summary states travel in the payload (ok/unavailable/failed/
  insufficient_evidence) — LLM absence is never an HTTP error.

Audit: one `intelligence.analyze` / `intelligence.summarize` row per request
with counts only — never document contents.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.exceptions import AppError, DatabaseUnavailableError
from app.intelligence.service import analyze_corpus, analyze_document, audit_metadata
from app.intelligence.summary import build_ai_summary, build_deterministic_summary
from app.intelligence.corpus import build_corpus
from app.intelligence.keywords import extract_keywords
from app.intelligence.topics import identify_topics, topic_document_matches
from app.intelligence.wordcloud import generate_word_cloud
from app.models import AuditLog
from app.schemas.intelligence import (
    CorpusAnalyzeRequest,
    CorpusAnalyzeResponse,
    IntelligenceResponse,
    KeywordsResponse,
    SummarizeRequest,
    SummarizeResponse,
    TopicsResponse,
    WordCloudResponse,
)

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])
logger = logging.getLogger(__name__)


def _log(db: Session, action: str, payload: dict) -> None:
    try:
        db.add(AuditLog(action=action, entity_type="intelligence",
                        entity_id=None, details=audit_metadata(payload)))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.warning("Intelligence audit write failed (result unaffected)")


@router.get("/documents/{document_id}", response_model=IntelligenceResponse)
def document_intelligence_route(document_id: int, db: Session = Depends(get_db)):
    """Full intelligence payload for one document (deterministic)."""
    try:
        payload = analyze_document(db, document_id)
    except DatabaseUnavailableError:
        raise
    except SQLAlchemyError as exc:
        logger.exception("Document intelligence failed at the database level")
        raise DatabaseUnavailableError from exc
    _log(db, "intelligence.analyze", payload)
    return IntelligenceResponse(**payload)


@router.get("/documents/{document_id}/keywords", response_model=KeywordsResponse)
def document_keywords_route(document_id: int, db: Session = Depends(get_db)):
    """Deterministic keyword/phrase ranking for one document."""
    try:
        corpus = build_corpus(db, [document_id])
        keyword_data = extract_keywords(corpus)
    except DatabaseUnavailableError:
        raise
    except SQLAlchemyError as exc:
        logger.exception("Keyword extraction failed at the database level")
        raise DatabaseUnavailableError from exc
    payload = {
        "scope": "document", "document_ids": [document_id],
        "keywords": [k.to_payload() for k in keyword_data["keywords"]],
        "corpus_stats": corpus.stats,
        "limitations": [],
    }
    return KeywordsResponse(
        document_id=document_id,
        keywords=payload["keywords"],
        corpus_stats=corpus.stats,
    )


@router.get("/documents/{document_id}/topics", response_model=TopicsResponse)
def document_topics_route(document_id: int, db: Session = Depends(get_db)):
    """Deterministic topics + topic-document relationships for one document."""
    try:
        corpus = build_corpus(db, [document_id])
        topic_data = identify_topics(corpus)
        matches = topic_document_matches(
            corpus, topic_data["topics"], topic_data["term_units"],
            topic_data["term_frequency"],
        )
    except DatabaseUnavailableError:
        raise
    except SQLAlchemyError as exc:
        logger.exception("Topic identification failed at the database level")
        raise DatabaseUnavailableError from exc
    return TopicsResponse(
        document_id=document_id,
        topics=[t.to_payload() for t in topic_data["topics"]],
        topic_document_matches=[m.to_payload() for m in matches],
        corpus_stats=corpus.stats,
    )


@router.get("/documents/{document_id}/word-cloud", response_model=WordCloudResponse)
def document_word_cloud_route(document_id: int, db: Session = Depends(get_db)):
    """Deterministic word-cloud DATA for one document (frontend renders)."""
    try:
        corpus = build_corpus(db, [document_id])
        cloud = generate_word_cloud(corpus)
    except DatabaseUnavailableError:
        raise
    except SQLAlchemyError as exc:
        logger.exception("Word-cloud generation failed at the database level")
        raise DatabaseUnavailableError from exc
    return WordCloudResponse(
        document_id=document_id,
        terms=[t.to_payload() for t in cloud],
        corpus_stats=corpus.stats,
    )


@router.post("/corpus/analyze", response_model=CorpusAnalyzeResponse)
def corpus_analyze_route(
    payload: CorpusAnalyzeRequest,
    db: Session = Depends(get_db),
):
    """Corpus-wide intelligence (bounded; empty body ⇒ whole corpus)."""
    try:
        result = analyze_corpus(db, payload.document_ids)
    except DatabaseUnavailableError:
        raise
    except SQLAlchemyError as exc:
        logger.exception("Corpus analysis failed at the database level")
        raise DatabaseUnavailableError from exc
    _log(db, "intelligence.analyze", result)
    return CorpusAnalyzeResponse(
        scope=result["scope"],
        document_ids=result["document_ids"],
        keywords=result["keywords"],
        topics=result["topics"],
        word_cloud=result["word_cloud"],
        topic_document_matches=result["topic_document_matches"],
        corpus_stats=result["corpus_stats"],
        limitations=result["limitations"],
    )


@router.post("/documents/{document_id}/summarize", response_model=SummarizeResponse)
def document_summarize_route(
    document_id: int,
    payload: SummarizeRequest,
    db: Session = Depends(get_db),
):
    """Deterministic summary; optional AI prose (opt-in, labeled, fallback-safe)."""
    try:
        corpus = build_corpus(db, [document_id])
        topic_data = identify_topics(corpus)
        summary = build_deterministic_summary(db, document_id, corpus, topic_data["topics"])
        ai_summary = None
        if payload.include_ai_summary:
            ai_summary = build_ai_summary(db, document_id, corpus)
    except DatabaseUnavailableError:
        raise
    except SQLAlchemyError as exc:
        logger.exception("Document summarization failed at the database level")
        raise DatabaseUnavailableError from exc
    audit_payload = {
        "scope": "document", "document_ids": [document_id],
        "corpus_stats": corpus.stats,
        "ai_summary": ai_summary or {},
    }
    _log(db, "intelligence.summarize", audit_payload)
    return SummarizeResponse(
        document_id=document_id,
        summary=summary.to_payload(),
        ai_summary=ai_summary,
    )
