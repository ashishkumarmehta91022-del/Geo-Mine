"""Deterministic ranking for search results.

Fixed arithmetic over factual signals — no LLM, no learned model, no
"trust score". Higher rank_sort = earlier in the result list. Ranking means
"likely relevant", never "factually correct".

Signals (in priority order):
1. exact phrase match in title/content     (+40 per phrase)
2. all keywords present                    (+15)
3. keyword prefix match on entity/metric   (+10 each)
4. keyword hits in title                   (+6 per keyword, capped)
5. text-search relevance (ts_rank) scaled  (+ up to 10)
6. record > page > validation tie-break    (+3 / +2 / +1)

Ties break by (unit_type priority, document_id, id) — fully deterministic.
"""

from app.constants import RetrievalUnitType

PHRASE_BONUS = 40.0
ALL_KEYWORDS_BONUS = 15.0
ENTITY_METRIC_PREFIX_BONUS = 10.0
TITLE_HIT_BONUS = 6.0
TITLE_HIT_CAP = 3
TSRANK_SCALE = 10.0

UNIT_PRIORITY = {
    RetrievalUnitType.RECORD: 3.0,
    RetrievalUnitType.PAGE: 2.0,
    RetrievalUnitType.VALIDATION: 1.0,
}


def rank_unit(
    *,
    phrases: tuple[str, ...],
    keywords: tuple[str, ...],
    title: str | None,
    content: str | None,
    entity: str | None,
    metric: str | None,
    unit_type: str,
    tsrank: float = 0.0,
) -> float:
    """Compute the deterministic rank score for one unit."""
    score = 0.0
    title_lower = (title or "").lower()
    content_lower = (content or "").lower()

    for phrase in phrases:
        needle = phrase.lower()
        if needle in title_lower or needle in content_lower:
            score += PHRASE_BONUS

    if keywords:
        hits = sum(1 for k in keywords if k.lower() in title_lower or k.lower() in content_lower)
        if hits == len(keywords):
            score += ALL_KEYWORDS_BONUS
        score += TITLE_HIT_BONUS * min(hits, TITLE_HIT_CAP)

    for keyword in keywords:
        needle = keyword.lower()
        if entity and entity.lower().startswith(needle):
            score += ENTITY_METRIC_PREFIX_BONUS
        if metric and metric.lower().startswith(needle):
            score += ENTITY_METRIC_PREFIX_BONUS

    if tsrank:
        score += min(max(tsrank, 0.0), 1.0) * TSRANK_SCALE

    score += UNIT_PRIORITY.get(unit_type, 0.0)
    return score
