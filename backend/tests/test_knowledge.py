"""Knowledge-layer tests that need no database: parser, ranking, unit drafts."""

from app.constants import RetrievalUnitType
from app.knowledge.query_parser import MAX_LIMIT, parse_search_query
from app.knowledge.ranking import rank_unit
from app.knowledge.units import (
    IndexUnitDraft,
    page_unit,
    record_unit,
    validation_unit,
)

# --- query parsing -----------------------------------------------------------


def test_parse_keyword_query():
    parsed = parse_search_query(q="production tonnes")
    assert parsed.keywords == ("production", "tonnes")
    assert parsed.phrases == ()
    assert parsed.has_text


def test_parse_phrase_and_keywords():
    parsed = parse_search_query(q='"coal production" DEMO')
    assert parsed.phrases == ("coal production",)
    assert parsed.keywords == ("DEMO",)


def test_parse_multiple_phrases():
    parsed = parse_search_query(q='"coal production" "DEMO_MINE_A"')
    assert parsed.phrases == ("coal production", "DEMO_MINE_A")


def test_filters_and_pagination_clamping():
    parsed = parse_search_query(
        q="production",
        document_id=3,
        page=4,
        entity="DEMO_MINE_A",
        metric="demo_coal_production",
        reporting_period="2025-06-30",
        extraction_method="ocr",
        validation_status="pass",
        limit=100000,
        offset=-5,
    )
    assert parsed.document_id == 3
    assert parsed.page == 4
    assert parsed.entity == "DEMO_MINE_A"
    assert parsed.limit == MAX_LIMIT  # clamped
    assert parsed.offset == 0  # negative offset clamped
    assert parsed.has_filters


def test_empty_query_has_no_text_and_no_filters():
    parsed = parse_search_query(q="")
    assert not parsed.has_text
    assert not parsed.has_filters


def test_long_query_is_truncated_safely():
    parsed = parse_search_query(q="x" * 5000)
    assert len(parsed.text) <= 300  # MAX_QUERY_LENGTH cap
    assert len(parsed.keywords) <= 20


# --- ranking -------------------------------------------------------------------


def test_phrase_match_outranks_plain_keyword():
    phrase_score = rank_unit(
        phrases=("coal production",),
        keywords=(),
        title="report",
        content="Annual coal production summary",
        entity=None,
        metric=None,
        unit_type=RetrievalUnitType.PAGE,
    )
    keyword_score = rank_unit(
        phrases=(),
        keywords=("coal",),
        title="report",
        content="Annual coal production summary",
        entity=None,
        metric=None,
        unit_type=RetrievalUnitType.PAGE,
    )
    assert phrase_score > keyword_score


def test_entity_metric_prefix_boost():
    with_boost = rank_unit(
        phrases=(), keywords=("demo",), title=None, content=None,
        entity="DEMO_MINE_A", metric=None, unit_type=RetrievalUnitType.PAGE,
    )
    without = rank_unit(
        phrases=(), keywords=("demo",), title=None, content=None,
        entity="OTHER", metric=None, unit_type=RetrievalUnitType.PAGE,
    )
    assert with_boost > without


def test_ranking_is_deterministic():
    args = dict(
        phrases=("production",),
        keywords=("tonnes",),
        title="T",
        content="C",
        entity="E",
        metric="M",
        unit_type=RetrievalUnitType.RECORD,
    )
    assert rank_unit(**args) == rank_unit(**args)


def test_same_input_same_ordering_key():
    """Two identical units produce identical scores — ordering is stable."""
    score_a = rank_unit(phrases=("x",), keywords=(), title="A", content=None,
                        entity=None, metric=None, unit_type=RetrievalUnitType.PAGE)
    score_b = rank_unit(phrases=("x",), keywords=(), title="A", content=None,
                        entity=None, metric=None, unit_type=RetrievalUnitType.PAGE)
    assert score_a == score_b


# --- unit drafts (pure functions) -------------------------------------------------


class _FakePage:
    def __init__(self):
        self.id = 11
        self.document_id = 2
        self.page_number = 4
        self.content_type = "page"
        self.extracted_text = "Native text about production"
        self.section_reference = "page 4"
        self.extraction_status = "extracted"
        self.structured_metadata = None


class _FakeRecord:
    def __init__(self):
        self.id = 21
        self.document_id = 2
        self.page_id = 11
        self.entity_name = "DEMO_MINE_A"
        self.metric_name = "demo_coal_production"
        self.metric_value = None
        self.value_raw = "1,200"
        self.normalized_value = "1200"
        self.unit = "tonnes"
        self.reporting_period = "2025-06-30"
        self.source_reference = "sheet Production, row 2"
        self.extraction_method = "spreadsheet"
        self.validation_status = "pass"


class _FakeValidation:
    def __init__(self):
        self.id = 31
        self.document_id = 2
        self.extracted_record_id = 21
        self.page_id = None
        self.rule_code = "CROSS_DOCUMENT_CONFLICT"
        self.status = "review_required"
        self.message = "Conflicting values…"
        self.source_reference = "sheet Production, row 2"


def test_page_unit_keeps_provenance():
    draft = page_unit(_FakePage(), "report.pdf")
    assert draft.unit_type == RetrievalUnitType.PAGE
    assert draft.page_id == 11
    assert draft.document_id == 2
    assert draft.source_reference == "page 4"
    assert draft.content == "Native text about production"
    assert draft.extraction_method == "native_text"


def test_record_unit_keeps_raw_and_normalized_distinction():
    draft = record_unit(_FakeRecord(), "report.pdf")
    assert draft.unit_type == RetrievalUnitType.RECORD
    assert draft.record_id == 21
    assert draft.entity == "DEMO_MINE_A"
    assert draft.metric == "demo_coal_production"
    assert draft.content == "1200"  # normalized preferred for search text
    assert draft.reporting_period == "2025-06-30"
    assert draft.validation_status == "pass"


def test_validation_unit_is_searchable_including_conflicts():
    draft = validation_unit(_FakeValidation(), "report.pdf")
    assert draft.unit_type == RetrievalUnitType.VALIDATION
    assert draft.validation_id == 31
    assert "CROSS_DOCUMENT_CONFLICT" in draft.title
    assert draft.validation_status == "review_required"
    assert draft.source_reference  # provenance kept
