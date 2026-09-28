"""Document & topic intelligence (Step 13).

Deterministic, rebuildable derived intelligence over the existing extraction
pipeline and knowledge index: bounded corpus, TF-IDF keywords, content-only
n-gram phrases, co-occurrence topics with derived labels, word-cloud data,
topic ↔ document relationships, deterministic summaries — plus an optional,
strictly grounded AI prose summary via the Step 10 provider abstraction.
"""

from app.intelligence.corpus import build_corpus
from app.intelligence.keywords import extract_keywords
from app.intelligence.models import (
    CorpusUnit,
    DocumentIntelligenceResult,
    DocumentSummary,
    Keyword,
    SourceRef,
    Topic,
    TopicDocumentMatch,
    WordCloudTerm,
)
from app.intelligence.service import analyze_corpus, analyze_document, audit_metadata
from app.intelligence.summary import (
    build_ai_summary,
    build_deterministic_summary,
    validate_ai_summary,
)
from app.intelligence.text import content_tokens, extract_ngrams, tokenize

__all__ = [
    "CorpusUnit",
    "DocumentIntelligenceResult",
    "DocumentSummary",
    "Keyword",
    "SourceRef",
    "Topic",
    "TopicDocumentMatch",
    "WordCloudTerm",
    "analyze_corpus",
    "analyze_document",
    "audit_metadata",
    "build_ai_summary",
    "build_corpus",
    "build_deterministic_summary",
    "content_tokens",
    "extract_keywords",
    "extract_ngrams",
    "tokenize",
    "validate_ai_summary",
]
