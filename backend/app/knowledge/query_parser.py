"""Search query parsing — deterministic, DB-free, injection-safe output.

Produces a SearchQuery dataclass; SQL construction happens later through
SQLAlchemy expression trees (never string interpolation). Parse errors are
impossible by construction: unknown filters are ignored, oversized queries
are truncated to safe limits.
"""

from dataclasses import dataclass, field

MAX_QUERY_LENGTH = 300
MAX_TERMS = 20
MAX_LIMIT = 100
DEFAULT_LIMIT = 20


@dataclass(frozen=True)
class SearchQuery:
    """A parsed search request."""

    text: str = ""
    phrases: tuple[str, ...] = field(default_factory=tuple)
    keywords: tuple[str, ...] = field(default_factory=tuple)
    document_id: int | None = None
    page: int | None = None
    entity: str | None = None
    metric: str | None = None
    reporting_period: str | None = None
    extraction_method: str | None = None
    validation_status: str | None = None
    limit: int = DEFAULT_LIMIT
    offset: int = 0

    @property
    def has_text(self) -> bool:
        return bool(self.phrases or self.keywords)

    @property
    def has_filters(self) -> bool:
        return any(
            value is not None
            for value in (
                self.document_id, self.page, self.entity, self.metric,
                self.reporting_period, self.extraction_method, self.validation_status,
            )
        )


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def parse_search_query(
    *,
    q: str | None = None,
    document_id: int | None = None,
    page: int | None = None,
    entity: str | None = None,
    metric: str | None = None,
    reporting_period: str | None = None,
    extraction_method: str | None = None,
    validation_status: str | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> SearchQuery:
    """Parse raw request parameters into a SearchQuery.

    - `q` supports `"exact phrase"` segments plus free keywords.
    - Text is length-capped; keyword count is capped (no query-size abuse).
    - limit is clamped to [1, MAX_LIMIT]; offset to >= 0.
    - Non-positive page numbers are normalized to None (page filter refers to
      the source page number, not pagination).
    """
    text_input = (q or "")[:MAX_QUERY_LENGTH].strip()

    # Deterministic pass: collect quoted phrases, strip them, keep keywords.
    phrases: list[str] = []
    rest_parts: list[str] = []
    buffer = text_input
    while '"' in buffer:
        before, _, after = buffer.partition('"')
        rest_parts.append(before)
        phrase, _, buffer = after.partition('"')
        if phrase.strip():
            phrases.append(phrase.strip())
    rest_parts.append(buffer)
    keywords = [token for token in " ".join(rest_parts).split() if token][:MAX_TERMS]

    clamped_limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    clamped_offset = max(0, int(offset or 0))
    page_filter = page if (page is not None and page > 0) else None

    return SearchQuery(
        text=text_input,
        phrases=tuple(phrases),
        keywords=tuple(keywords),
        document_id=document_id if document_id is not None and document_id > 0 else None,
        page=page_filter,
        entity=_clean(entity),
        metric=_clean(metric),
        reporting_period=_clean(reporting_period),
        extraction_method=_clean(extraction_method),
        validation_status=_clean(validation_status),
        limit=clamped_limit,
        offset=clamped_offset,
    )
