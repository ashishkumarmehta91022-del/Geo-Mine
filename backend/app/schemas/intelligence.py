"""Document intelligence API schemas (Step 13)."""

from typing import Any

from pydantic import BaseModel, Field


class CorpusAnalyzeRequest(BaseModel):
    """Corpus-wide analysis request (empty/omitted document_ids ⇒ whole corpus)."""

    document_ids: list[int] | None = None


class SummarizeRequest(BaseModel):
    """Document summarize request — AI prose is opt-in; deterministic by default."""

    include_ai_summary: bool = False


class IntelligenceResponse(BaseModel):
    """Full document/corpus intelligence payload (mirrors service output)."""

    scope: str
    document_ids: list[int] = []
    keywords: list[dict[str, Any]] = []
    topics: list[dict[str, Any]] = []
    word_cloud: list[dict[str, Any]] = []
    topic_document_matches: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    corpus_stats: dict[str, Any] = {}
    ai_summary: dict[str, Any] | None = None
    limitations: list[str] = []
    summary: dict[str, Any] | None = None


class KeywordsResponse(BaseModel):
    document_id: int
    keywords: list[dict[str, Any]] = []
    corpus_stats: dict[str, Any] = {}
    limitations: list[str] = []


class TopicsResponse(BaseModel):
    document_id: int
    topics: list[dict[str, Any]] = []
    topic_document_matches: list[dict[str, Any]] = []
    corpus_stats: dict[str, Any] = {}
    limitations: list[str] = []


class WordCloudResponse(BaseModel):
    document_id: int
    terms: list[dict[str, Any]] = []
    corpus_stats: dict[str, Any] = {}
    limitations: list[str] = []


class SummarizeResponse(BaseModel):
    document_id: int
    summary: dict[str, Any]
    ai_summary: dict[str, Any] | None = None
    limitations: list[str] = []


class CorpusAnalyzeResponse(BaseModel):
    scope: str = "corpus"
    document_ids: list[int] = []
    keywords: list[dict[str, Any]] = []
    topics: list[dict[str, Any]] = []
    word_cloud: list[dict[str, Any]] = []
    topic_document_matches: list[dict[str, Any]] = []
    corpus_stats: dict[str, Any] = {}
    limitations: list[str] = []
