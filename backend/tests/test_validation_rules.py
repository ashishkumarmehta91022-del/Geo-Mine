"""Validation engine tests (no PostgreSQL required) — deterministic by design."""

from decimal import Decimal

from app.constants import ValidationSeverity, ValidationStatus
from app.validation.config import (
    NumericSpec,
    RangeSpec,
    ValidationConfig,
    demo_config,
)
from app.validation.engine import run_validation
from app.validation.models import ValueCandidate
from app.validation.parsing import parse_date, parse_number
from app.validation.rules import (
    CROSS_DOCUMENT_CONFLICT,
    DATE_FUTURE,
    DATE_INVALID,
    DUPLICATE_DETECTED,
    NUMERIC_FORMAT,
    NUMERIC_NEGATIVE,
    OCR_LOW_CONFIDENCE,
    RANGE_OUT_OF_BOUNDS,
    REQUIRED_FIELD_MISSING,
)

# --- helpers -----------------------------------------------------------------


def candidate(
    record_id=1,
    document_id=1,
    entity="DEMO_MINE_A",
    metric="DEMO_COAL_PRODUCTION",
    raw="1200",
    numeric=True,
    period="2025-06-30",
    confidence=None,
    review_required=False,
    unit="tonnes",
) -> ValueCandidate:
    # Mirror reality: an unparseable raw value arrives with numeric_value=None.
    parsed = None
    if numeric and raw is not None:
        try:
            parsed = Decimal(raw)
        except Exception:  # noqa: BLE001 — e.g. "1O5" with letter O
            parsed = None
    return ValueCandidate(
        document_id=document_id,
        metric_name=metric,
        raw_value=raw,
        numeric_value=parsed,
        record_id=record_id,
        entity_name=entity,
        unit=unit,
        reporting_period=period,
        source_reference=f"page 1, row {record_id}",
        confidence=confidence,
        review_required=review_required,
    )


def base_config(**overrides) -> ValidationConfig:
    config = demo_config()
    if overrides:
        config = ValidationConfig(
            **{**config.__dict__, **overrides}
        )
    return config


# --- parsing -------------------------------------------------------------------


def test_parse_number_handles_grouping_and_signs():
    assert parse_number("1200") == Decimal("1200")
    assert parse_number("1,200") == Decimal("1200")
    assert parse_number("1,20,000") == Decimal("120000")  # Indian grouping
    assert parse_number("-45.5") == Decimal("-45.5")
    assert parse_number(" 12 ") == Decimal("12")


def test_parse_number_refuses_non_numbers():
    assert parse_number("1O5") is None  # letter O — never guessed as 105
    assert parse_number("12.3.4") is None
    assert parse_number("") is None
    assert parse_number(None) is None


def test_parse_date_formats_and_refusals():
    assert parse_date("2025-06-30").isoformat() == "2025-06-30"
    assert parse_date("30/06/2025").isoformat() == "2025-06-30"
    assert parse_date("30-06-2025") is not None
    assert parse_date("31/02/2025") is None  # impossible calendar date
    assert parse_date("not a date") is None


# --- required fields ----------------------------------------------------------------


def test_missing_required_field_generates_error():
    outcomes = run_validation(
        [candidate(entity=None)], base_config()
    )
    missing = [o for o in outcomes if o.rule_code == REQUIRED_FIELD_MISSING]
    assert missing, "missing entity_name must be flagged"
    assert all(o.status == ValidationStatus.ERROR for o in missing)
    assert missing[0].severity == ValidationSeverity.ERROR
    assert "entity_name" in missing[0].message


def test_present_required_fields_produce_no_required_outcomes():
    outcomes = run_validation([candidate()], base_config())
    assert not [o for o in outcomes if o.rule_code == REQUIRED_FIELD_MISSING]


# --- numeric ----------------------------------------------------------------------------


def test_valid_number_passes():
    assert not run_validation([candidate(raw="1200")], base_config())


def test_invalid_numeric_format_flags_error_and_keeps_raw():
    bad = candidate(raw="1O5")  # letter O — classic OCR confusion
    outcomes = run_validation([bad], base_config())
    fmt = [o for o in outcomes if o.rule_code == NUMERIC_FORMAT]
    assert fmt and fmt[0].status == ValidationStatus.ERROR
    assert fmt[0].details["raw"] == "1O5"  # raw preserved verbatim
    assert "no correction" in fmt[0].message


def test_negative_value_behavior_is_configurable():
    outcomes = run_validation([candidate(raw="-50")], base_config())
    assert any(o.rule_code == NUMERIC_NEGATIVE for o in outcomes)

    allow = base_config(
        numeric_fields={FIELD_VALUE_KEY: NumericSpec(allow_negative=True)}
    )
    assert not any(
        o.rule_code == NUMERIC_NEGATIVE for o in run_validation([candidate(raw="-50")], allow)
    )


FIELD_VALUE_KEY = "metric_value"  # kept near tests for readability


def test_integer_expectation_flags_decimals_as_warning():
    config = base_config(numeric_fields={FIELD_VALUE_KEY: NumericSpec(integer_only=True)})
    outcomes = run_validation([candidate(raw="1200.5")], config)
    assert any(
        o.status == ValidationStatus.WARNING and o.expected == "integer" for o in outcomes
    )


# --- range --------------------------------------------------------------------------------


def test_range_boundaries_inclusive():
    config = base_config(ranges={FIELD_VALUE_KEY: RangeSpec(minimum=0, maximum=1200, inclusive=True)})
    assert not run_validation([candidate(raw="1200")], config)  # boundary inside

    exclusive = base_config(ranges={FIELD_VALUE_KEY: RangeSpec(minimum=0, maximum=1200, inclusive=False)})
    outcomes = run_validation([candidate(raw="1200")], exclusive)
    assert any(o.rule_code == RANGE_OUT_OF_BOUNDS for o in outcomes)


def test_out_of_range_uses_configured_status():
    config = base_config(ranges={FIELD_VALUE_KEY: RangeSpec(minimum=0, maximum=100, status="error")})
    outcomes = run_validation([candidate(raw="150")], config)
    assert outcomes[0].status == ValidationStatus.ERROR

    warn_config = base_config(ranges={FIELD_VALUE_KEY: RangeSpec(minimum=0, maximum=100, status="warning")})
    outcomes = run_validation([candidate(raw="150")], warn_config)
    assert outcomes[0].status == ValidationStatus.WARNING


# --- dates ------------------------------------------------------------------------------------


def test_invalid_date_flags_warning_and_keeps_raw():
    outcomes = run_validation(
        [candidate(period="31/02/2025")], base_config()
    )
    invalid = [o for o in outcomes if o.rule_code == DATE_INVALID]
    assert invalid
    assert invalid[0].details["raw"] == "31/02/2025"  # original preserved


def test_future_date_flagged_when_configured():
    from app.validation.config import DateSpec

    outcomes = run_validation(
        [candidate(period="2099-01-01")], base_config()
    )
    assert any(o.rule_code == DATE_FUTURE for o in outcomes)

    allow_future = base_config(
        date_fields={"reporting_period": DateSpec(allow_future=True)}
    )
    assert not any(
        o.rule_code == DATE_FUTURE
        for o in run_validation([candidate(period="2099-01-01")], allow_future)
    )


# --- OCR confidence -------------------------------------------------------------------------------


def test_high_confidence_ocr_passes():
    outcomes = run_validation(
        [candidate(confidence=0.95)], base_config()
    )
    assert not [o for o in outcomes if o.rule_code == OCR_LOW_CONFIDENCE]


def test_low_confidence_ocr_requires_review():
    outcomes = run_validation(
        [candidate(confidence=0.42, raw="1O5")], base_config()
    )
    review = [o for o in outcomes if o.rule_code == OCR_LOW_CONFIDENCE]
    assert review
    assert review[0].status == ValidationStatus.REVIEW_REQUIRED
    assert review[0].candidate.raw_value == "1O5"  # verbatim
    assert review[0].details["confidence"] == 0.42


def test_upstream_review_flag_enters_review_even_without_confidence():
    outcomes = run_validation(
        [candidate(review_required=True)], base_config()
    )
    assert any(o.status == ValidationStatus.REVIEW_REQUIRED for o in outcomes)


# --- duplicates -------------------------------------------------------------------------------------


def test_unique_records_do_not_trigger_duplicates():
    outcomes = run_validation(
        [candidate(record_id=1, period="2025-06-30"), candidate(record_id=2, period="2025-09-30")],
        base_config(),
    )
    assert not [o for o in outcomes if o.rule_code == DUPLICATE_DETECTED]


def test_duplicate_key_generates_warning_and_keeps_both():
    first = candidate(record_id=1)
    second = candidate(record_id=2)
    outcomes = run_validation([first, second], base_config())
    duplicates = [o for o in outcomes if o.rule_code == DUPLICATE_DETECTED]
    assert len(duplicates) == 1
    assert duplicates[0].status == ValidationStatus.WARNING
    assert duplicates[0].details["first_record_id"] == 1
    assert duplicates[0].candidate.record_id == 2  # both still exist — nothing deleted


# --- cross-document conflicts -------------------------------------------------------------------------


def test_cross_document_conflict_preserves_both_sides():
    a = candidate(record_id=1, document_id=1, raw="1200", entity="DEMO_MINE_A", period="2025-06-30")
    b = candidate(record_id=2, document_id=2, raw="1350", entity="DEMO_MINE_A", period="2025-06-30")
    outcomes = run_validation([a, b], base_config())

    conflicts = [o for o in outcomes if o.rule_code == CROSS_DOCUMENT_CONFLICT]
    assert len(conflicts) == 1
    assert conflicts[0].status == ValidationStatus.REVIEW_REQUIRED
    values = conflicts[0].details["values"]
    assert {v["value"] for v in values} == {"1200", "1350"}  # BOTH preserved
    assert {v["document_id"] for v in values} == {1, 2}
    assert all(v["source_reference"] for v in values)  # provenance kept
    assert "No winner selected" in conflicts[0].message


def test_same_value_across_documents_is_not_a_conflict():
    a = candidate(record_id=1, document_id=1, raw="1200")
    b = candidate(record_id=2, document_id=2, raw="1200")
    outcomes = run_validation([a, b], base_config())
    assert not [o for o in outcomes if o.rule_code == CROSS_DOCUMENT_CONFLICT]


def test_different_entities_are_not_conflicts():
    a = candidate(record_id=1, document_id=1, entity="DEMO_MINE_A")
    b = candidate(record_id=2, document_id=2, entity="DEMO_MINE_B")
    outcomes = run_validation([a, b], base_config())
    assert not [o for o in outcomes if o.rule_code == CROSS_DOCUMENT_CONFLICT]


# --- engine guarantees --------------------------------------------------------------------------------


def test_same_input_same_output_determinism():
    """Same candidates (same order) + same config ⇒ identical outcomes."""
    candidates = [
        candidate(record_id=1),
        candidate(record_id=2, raw="1O5"),
        candidate(record_id=3, document_id=2, raw="1200"),
    ]
    first = run_validation(list(candidates), base_config())
    second = run_validation(list(candidates), base_config())
    assert [(o.rule_code, o.status, o.message, o.candidate.record_id) for o in first] == [
        (o.rule_code, o.status, o.message, o.candidate.record_id) for o in second
    ]
    # Also: re-running with the same set of candidates produces the same
    # outcome SET (order-independent aggregation of identical inputs).
    third = run_validation(
        [candidates[2], candidates[0], candidates[1]], base_config()
    )
    assert sorted((o.rule_code, o.status) for o in third) == sorted(
        (o.rule_code, o.status) for o in first
    )


def test_validation_never_mutates_candidates():
    target = candidate(raw="1200")
    run_validation([target, candidate(record_id=2)], base_config())
    assert target.raw_value == "1200"  # source value untouched
    assert target.numeric_value == Decimal("1200")
