"""Safe numeric conversion for analytics (Step 12).

Arithmetic uses ONLY stored normalized values (Step 7 guarantees: value_raw
is verbatim and may contain OCR artifacts such as "1O5" — it is never parsed,
never "corrected"). A normalized value participates in arithmetic only when
it parses as a finite plain number; otherwise the raw value is preserved and
the record is EXCLUDED with an explicit reason — never silently converted.
"""

from decimal import Decimal, InvalidOperation
from typing import Any

# Reasons recorded on excluded records (explicit, deterministic).
REASON_NO_NORMALIZED_VALUE = "no_safe_normalized_value"
REASON_NON_NUMERIC = "normalized_value_not_numeric"
REASON_NOT_FINITE = "normalized_value_not_finite"
REASON_CONFLICT = "conflicting_values_not_averaged"
REASON_VALIDATION_ERROR = "validation_status_error_or_review"


def parse_numeric(normalized_value: str | None) -> Decimal | None:
    """Parse a stored normalized value into a Decimal, or None when unsafe.

    Accepts plain decimal numbers only ("1200", "-3.25", "1e3"). Rejects
    empty strings, thousands separators ("1,200"), unit-suffixed text and
    non-finite values — everything uncertain is excluded, not guessed.
    """
    if normalized_value is None:
        return None
    text = normalized_value.strip()
    if not text:
        return None
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if not value.is_finite():
        return None
    return value


def exclusion_entry(record, reason: str) -> dict[str, Any]:
    """Deterministic exclusion record: raw value preserved, reason explicit."""
    return {
        "record_id": record.record_id,
        "document_id": record.document_id,
        "value_raw": record.value_raw,
        "normalized_value": record.normalized_value,
        "reason": reason,
    }
