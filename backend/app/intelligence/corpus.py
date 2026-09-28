"""Corpus construction for document intelligence (Step 13).

Builds a bounded, deterministic text corpus from the EXISTING knowledge
index (Step 8) — indexed page/record content, never re-read from original
binary files. Every unit keeps full provenance (document/page/unit ids and
source reference). Original documents are never modified.

Bounds (documented limits, deterministic):
- MAX_CORPUS_DOCUMENTS — documents per corpus analysis
- MAX_UNITS_PER_DOCUMENT — indexed units per document
- MAX_CHARS_PER_UNIT — text characters used per unit
- MAX_CORPUS_UNITS / MAX_CORPUS_CHARS — whole-corpus caps
Exceeding a bound marks the corpus `truncated` (honest, never silent).
"""

from collections import Counter
from dataclasses import replace
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.exceptions import AppError, DatabaseUnavailableError
from app.intelligence.text import TOKEN_PATTERN, content_tokens, tokenize
from app.intelligence.models import CorpusUnit
from app.models import Document, DocumentPage

# --- documented bounds -------------------------------------------------------
MAX_CORPUS_DOCUMENTS = 50
MAX_UNITS_PER_DOCUMENT = 120
MAX_CHARS_PER_UNIT = 4_000
MAX_CORPUS_UNITS = 600
MAX_CORPUS_CHARS = 240_000
MAX_TERM_SOURCES = 8               # provenance refs kept per term
MAX_UNIT_SNIPPET = 400             # snippet size for AI evidence


def _flatten(text: str | None, limit: int = MAX_CHARS_PER_UNIT) -> str:
    return " ".join((text or "").split())[:limit]


class CorpusData:
    """The built corpus + deterministic stats (in-memory, rebuildable)."""

    def __init__(self) -> None:
        self.units: list[CorpusUnit] = []
        self.display_forms: dict[str, str] = {}
        self.document_ids: list[int] = []
        self.stats: dict[str, Any] = {}

    @property
    def total_chars(self) -> int:
        return sum(len(" ".join(unit.tokens)) for unit in self.units)


def build_corpus(db: Session, document_ids: list[int] | None = None) -> CorpusData:
    """Build the intelligence corpus from knowledge_index content.

    `document_ids=None` (or empty) ⇒ whole corpus (all indexed documents),
    bounded. Raises DatabaseUnavailableError honestly when PostgreSQL is
    unreachable; raises 404 NotFoundError when a requested document has no
    indexed units at all.
    """
    try:
        stmt = (
            select(Document.id, Document.filename)
            .order_by(Document.id)
            .limit(MAX_CORPUS_DOCUMENTS + 1)
        )
        if document_ids:
            stmt = stmt.where(Document.id.in_(document_ids))
        documents = dict(db.execute(stmt).all())

        missing = set(document_ids or []) - set(documents)
        if missing:
            raise AppError(
                status_code=404,
                code="document_not_found",
                message=f"Document(s) not found: {sorted(missing)}.",
            )

        corpus = CorpusData()
        corpus.document_ids = sorted(documents)

        unit_budget = MAX_CORPUS_UNITS
        char_budget = MAX_CORPUS_CHARS
        chars_used = 0
        truncated_units = False
        truncated_chars = False

        for document_id in corpus.document_ids:
            if unit_budget <= 0 or char_budget <= 0:
                truncated_units = True
                break
            from app.models import KnowledgeIndex

            rows = list(
                db.execute(
                    select(
                        KnowledgeIndex.id,
                        KnowledgeIndex.page_id,
                        KnowledgeIndex.unit_type,
                        KnowledgeIndex.content,
                        KnowledgeIndex.source_reference,
                    )
                    .where(KnowledgeIndex.document_id == document_id)
                    .order_by(KnowledgeIndex.id)
                    .limit(MAX_UNITS_PER_DOCUMENT + 1)
                ).all()
            )
            if len(rows) > MAX_UNITS_PER_DOCUMENT:
                rows = rows[:MAX_UNITS_PER_DOCUMENT]
                truncated_units = True
            if not rows and len(corpus.document_ids) == 1:
                # A single requested document with no indexed content is an
                # honest 404 (extraction/indexing has not produced anything).
                raise AppError(
                    status_code=404,
                    code="no_indexed_content",
                    message=(
                        "Document has no indexed content; process and index "
                        "it first (Steps 4-8)."
                    ),
                )

            for row in rows[:unit_budget]:
                text = _flatten(row.content)
                if len(text) > char_budget:
                    text = text[:char_budget]
                    truncated_chars = True
                char_budget -= len(text)
                chars_used += len(text)
                unit_budget -= 1
                tokens = tokenize(text)
                corpus.units.append(
                    CorpusUnit(
                        unit_id=len(corpus.units),
                        document_id=document_id,
                        page_id=row.page_id,
                        page_number=None,  # resolved lazily by the service
                        unit_type=row.unit_type,
                        source_reference=row.source_reference,
                        tokens=content_tokens(tokens),
                    )
                )
                # Display forms: most frequent original surface per token.
                for surface in TOKEN_PATTERN.findall(text):
                    key = surface.lower()
                    corpus.display_forms.setdefault(key, Counter())
                    corpus.display_forms[key][surface] += 1

        # Resolve page numbers for provenance in one batched read.
        page_ids = {unit.page_id for unit in corpus.units if unit.page_id is not None}
        if page_ids:
            page_numbers = dict(
                db.execute(
                    select(DocumentPage.id, DocumentPage.page_number).where(
                        DocumentPage.id.in_(page_ids)
                    )
                ).all()
            )
            corpus.units = [
                replace(unit, page_number=page_numbers.get(unit.page_id))
                if unit.page_id is not None
                else unit
                for unit in corpus.units
            ]

        corpus.stats = {
            "document_count": len(corpus.document_ids),
            "unit_count": len(corpus.units),
            "char_count": chars_used,
            "truncated_units": truncated_units,
            "truncated_chars": truncated_chars,
            "limits": {
                "max_documents": MAX_CORPUS_DOCUMENTS,
                "max_units_per_document": MAX_UNITS_PER_DOCUMENT,
                "max_chars_per_unit": MAX_CHARS_PER_UNIT,
                "max_units": MAX_CORPUS_UNITS,
                "max_chars": MAX_CORPUS_CHARS,
            },
        }
        return corpus
    except DatabaseUnavailableError:
        raise
    except OperationalError as exc:
        raise DatabaseUnavailableError from exc
    except SQLAlchemyError as exc:
        raise AppError(
            status_code=500,
            code="database_error",
            message="Could not build the intelligence corpus.",
        ) from exc


def display_form(corpus: CorpusData, term: str) -> str:
    """Preserved display form for a normalized term (deterministic)."""
    counter = corpus.display_forms.get(term)
    if not counter:
        return term
    most_common = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return most_common[0][0]
