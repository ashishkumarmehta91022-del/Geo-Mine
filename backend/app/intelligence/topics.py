"""Deterministic topic identification (Step 13, Phases 6 + 9).

Topics are keyword clusters derived from the actual corpus: ranked terms are
grouped by co-occurrence within corpus units. Labels come from the
underlying terms ("production / output") — never fabricated domain names.
Topic ↔ document relationships keep score, supporting terms and source
references for future navigation.
"""

from collections import Counter, defaultdict
from typing import Any

from app.intelligence.corpus import MAX_TERM_SOURCES, CorpusData
from app.intelligence.keywords import (
    MAX_KEYWORDS,
    MIN_TERM_FREQUENCY,
    _safe_idf,
    extract_keywords,
)
from app.intelligence.models import SourceRef, Topic, TopicDocumentMatch
from app.intelligence.text import content_tokens, phrase_key

# Bounds (documented, deterministic).
MAX_TOPICS = 12
MAX_TERMS_PER_TOPIC = 6
MAX_DOCS_PER_TOPIC = 20
MIN_TOPIC_SCORE = 1.0
TOPIC_LABEL_TERMS = 2


def _unit_content_tokens(unit) -> list[str]:
    return content_tokens(unit.tokens)


def identify_topics(corpus: CorpusData) -> dict[str, Any]:
    """Cluster ranked terms by unit co-occurrence (deterministic).

    Algorithm (documented, no framework):
    1. rank content terms by TF-IDF (keywords module)
    2. seed clusters with the strongest terms, then attach co-occurring
       terms (shared units, Jaccard-style overlap ≥ threshold)
    3. score a topic by the summed TF-IDF of its members; label = strongest
       member terms joined with " / " (derived, never fabricated)
    """
    keyword_data = extract_keywords(corpus)
    term_frequency = keyword_data["term_frequency"]
    doc_frequency = keyword_data["doc_frequency"]
    total_docs = max(len(corpus.document_ids), 1)

    # Term → set of unit ids (bounded by MIN_TERM_FREQUENCY).
    term_units: defaultdict[str, set[int]] = defaultdict(set)
    for unit in corpus.units:
        for token in set(unit.tokens):
            term_units[token].add(unit.unit_id)

    ranked = [
        term
        for term, freq in sorted(
            term_frequency.items(), key=lambda item: (-item[1], item[0])
        )
        if freq >= MIN_TERM_FREQUENCY and len(term) >= 3
    ][:MAX_KEYWORDS]

    assigned: set[str] = set()
    clusters: list[list[str]] = []
    for seed in ranked:
        if seed in assigned:
            continue
        seed_units = term_units[seed]
        cluster = [seed]
        assigned.add(seed)
        for candidate in ranked:
            if candidate in assigned:
                continue
            candidate_units = term_units[candidate]
            overlap = len(seed_units & candidate_units) / max(
                len(seed_units | candidate_units), 1
            )
            if overlap >= 0.3:
                cluster.append(candidate)
                assigned.add(candidate)
        clusters.append(cluster)
        if len(clusters) >= MAX_TOPICS:
            break

    topics: list[Topic] = []
    for index, cluster in enumerate(clusters, start=1):
        scored = sorted(
            cluster,
            key=lambda term: (
                -(term_frequency[term] * _safe_idf(corpus, doc_frequency[term])),
                term,
            ),
        )[:MAX_TERMS_PER_TOPIC]
        score = sum(
            term_frequency[term] * _safe_idf(corpus, doc_frequency[term])
            for term in scored
        )
        unit_ids = sorted(
            {uid for term in scored for uid in term_units[term]}
        )
        sources: list[SourceRef] = []
        seen: set[tuple[int, int | None, str]] = set()
        for unit_id in unit_ids:
            if len(sources) >= MAX_TERM_SOURCES:
                break
            unit = corpus.units[unit_id]
            key = (unit.document_id, unit.page_id, unit.source_reference or "")
            if key in seen:
                continue
            seen.add(key)
            sources.append(SourceRef(
                document_id=unit.document_id,
                page_id=unit.page_id,
                unit_type=unit.unit_type,
                source_reference=unit.source_reference,
            ))
        topics.append(Topic(
            topic_id=f"t{index}",
            label=" / ".join(
                term.title() if term.islower() else term
                for term in scored[:TOPIC_LABEL_TERMS]
            ),
            score=score,
            representative_terms=scored,
            document_ids=sorted({corpus.units[u].document_id for u in unit_ids}),
            sources=sources,
        ))
    topics = [t for t in topics if t.score >= MIN_TOPIC_SCORE]
    return {
        "topics": topics,
        "term_units": term_units,
        "term_frequency": term_frequency,
        "doc_frequency": doc_frequency,
    }


def topic_document_matches(
    corpus: CorpusData,
    topics: list[Topic],
    term_units: dict[str, set[int]],
    term_frequency: Counter,
) -> list[TopicDocumentMatch]:
    """Topic ↔ document relationships with score + supporting terms."""
    matches: list[TopicDocumentMatch] = []
    for topic in topics:
        per_document: defaultdict[int, dict[str, Any]] = defaultdict(
            lambda: {"units": set(), "terms": set()}
        )
        for term in topic.representative_terms:
            for unit_id in term_units.get(term, set()):
                unit = corpus.units[unit_id]
                entry = per_document[unit.document_id]
                entry["units"].add(unit_id)
                entry["terms"].add(term)
        for document_id in sorted(per_document):
            entry = per_document[document_id]
            doc_topic_terms = sorted(entry["terms"])
            score = sum(
                term_frequency.get(term, 0) for term in doc_topic_terms
            )
            sources: list[SourceRef] = []
            seen: set[tuple[int, int | None, str]] = set()
            for unit_id in sorted(entry["units"]):
                if len(sources) >= MAX_TERM_SOURCES:
                    break
                unit = corpus.units[unit_id]
                key = (unit.document_id, unit.page_id, unit.source_reference or "")
                if key in seen:
                    continue
                seen.add(key)
                sources.append(SourceRef(
                    document_id=unit.document_id,
                    page_id=unit.page_id,
                    unit_type=unit.unit_type,
                    source_reference=unit.source_reference,
                ))
            matches.append(TopicDocumentMatch(
                topic_id=topic.topic_id,
                topic_label=topic.label,
                document_id=document_id,
                score=float(score),
                supporting_terms=doc_topic_terms,
                sources=sources,
            ))
    matches.sort(key=lambda m: (m.topic_id, -m.score, m.document_id))
    return matches[:MAX_TOPICS * MAX_DOCS_PER_TOPIC]
