"""Deterministic keyword extraction (Step 13, Phases 4-5).

TF-IDF-style ranking over the bounded corpus — no AI judgment, no hidden
weights. Scores are explained (`score_reason`), ordering is deterministic
(score desc, frequency desc, term asc), and every term keeps bounded
provenance (source units). Phrases come from content-only n-grams (2-3
tokens, stopword-filtered) — no hardcoded domain terms.
"""

import math
from collections import Counter, defaultdict
from typing import Any

from app.intelligence.corpus import MAX_TERM_SOURCES, CorpusData
from app.intelligence.models import Keyword, SourceRef, TermKind
from app.intelligence.text import MAX_PHRASE_TOKENS, extract_ngrams, phrase_key

# Ranking bounds.
MAX_KEYWORDS = 60
MAX_PHRASES = 30
MIN_TERM_FREQUENCY = 2
MIN_PHRASE_FREQUENCY = 2
MIN_TERM_LENGTH = 3


def _source_refs(corpus: CorpusData, unit_ids: list[int]) -> list[SourceRef]:
    """Bounded, deduplicated provenance refs for one term."""
    refs: list[SourceRef] = []
    seen: set[tuple[int, int | None, str]] = set()
    for unit_id in unit_ids:
        unit = corpus.units[unit_id]
        key = (unit.document_id, unit.page_id, unit.source_reference or "")
        if key in seen or len(refs) >= MAX_TERM_SOURCES:
            continue
        seen.add(key)
        refs.append(SourceRef(
            document_id=unit.document_id,
            page_id=unit.page_id,
            unit_type=unit.unit_type,
            source_reference=unit.source_reference,
        ))
    return refs


def _safe_idf(corpus: CorpusData, document_frequency: int) -> float:
    """Smoothed IDF — always positive; a 1-document corpus still ranks."""
    total_docs = max(len(corpus.document_ids), 1)
    return math.log((total_docs + 1) / (document_frequency + 1)) + 1.0


def _display_form(corpus: CorpusData, term: str) -> str:
    """Deterministic display form: most frequent surface, capitalized."""
    from app.intelligence.corpus import display_form as corpus_display

    surface = corpus_display(corpus, term)
    if surface.islower():
        return " ".join(part.capitalize() for part in surface.split())
    return surface


def extract_keywords(corpus: CorpusData) -> dict[str, Any]:
    """Rank unigrams and phrases; returns keywords + term-frequency data.

    Score = frequency × smoothed idf(document_frequency). `score_reason`
    explains the signal in one deterministic string. Ordering is fully
    deterministic (score desc, frequency desc, term asc).
    """
    units = corpus.units
    total_docs = max(len(corpus.document_ids), 1)

    # --- unigrams -----------------------------------------------------------
    term_frequency: Counter = Counter()
    term_docs: defaultdict[str, set[int]] = defaultdict(set)
    term_units: defaultdict[str, list[int]] = defaultdict(list)
    for unit in units:
        for token, count in Counter(unit.tokens).items():
            term_frequency[token] += count
            term_docs[token].add(unit.document_id)
            term_units[token].append(unit.unit_id)

    doc_frequency: dict[str, int] = {
        term: len(docs) for term, docs in term_docs.items()
    }

    # --- phrases (2..3 content tokens) --------------------------------------
    phrase_frequency: Counter = Counter()
    phrase_docs: defaultdict[str, set[int]] = defaultdict(set)
    phrase_units: defaultdict[str, list[int]] = defaultdict(list)
    for unit in units:
        for phrase in extract_ngrams(unit.tokens, n_max=MAX_PHRASE_TOKENS):
            key = phrase_key(phrase)
            phrase_frequency[key] += 1
            phrase_docs[key].add(unit.document_id)
            phrase_units[key].append(unit.unit_id)

    phrases = [
        (term, freq, len(phrase_docs[term]), phrase_units[term])
        for term, freq in phrase_frequency.items()
        if freq >= MIN_PHRASE_FREQUENCY
        and len(phrase_docs[term]) >= 1
        and all(len(part) >= MIN_TERM_LENGTH for part in term.split())
    ]
    phrases.sort(key=lambda item: (-item[1], -item[2], item[0]))

    keywords: list[Keyword] = []
    for term, freq, df, unit_ids in phrases[:MAX_PHRASES]:
        score = freq * _safe_idf(corpus, df)
        keywords.append(Keyword(
            term=term,
            display_term=_display_form(corpus, term),
            kind=TermKind.PHRASE.value,
            frequency=freq,
            document_frequency=df,
            score=score,
            score_reason=(
                f"phrase frequency {freq} × smoothed idf({df} of {total_docs} docs)"
            ),
            sources=_source_refs(corpus, unit_ids),
        ))

    eligible = [
        (term, freq, doc_frequency[term], term_units[term])
        for term, freq in term_frequency.items()
        if freq >= MIN_TERM_FREQUENCY and len(term) >= MIN_TERM_LENGTH
    ]
    eligible.sort(key=lambda item: (-item[1], -item[2], item[0]))
    for term, freq, df, unit_ids in eligible[:MAX_KEYWORDS]:
        score = freq * _safe_idf(corpus, df)
        keywords.append(Keyword(
            term=term,
            display_term=_display_form(corpus, term),
            kind=TermKind.TERM.value,
            frequency=freq,
            document_frequency=df,
            score=score,
            score_reason=(
                f"frequency {freq} × smoothed idf({df} of {total_docs} docs)"
            ),
            sources=_source_refs(corpus, unit_ids),
        ))

    return {
        "keywords": keywords,
        "term_frequency": term_frequency,
        "doc_frequency": doc_frequency,
    }
