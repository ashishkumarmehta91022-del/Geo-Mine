"""Safe, deterministic normalization.

Contract: normalization only transforms values when the meaning is
unambiguous. When it isn't (e.g. OCR text "1O5"), the raw value is kept and
`normalized_value` stays NULL — never a guess.
"""

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from app.validation.parsing import parse_date, parse_number


def normalize_text(raw: str | None) -> str | None:
    """Whitespace + Unicode NFC normalization; None passthrough for empty."""
    if raw is None:
        return None
    text = unicodedata.normalize("NFC", raw).strip()
    if not text:
        return None
    # Collapse internal whitespace runs (incl. non-breaking spaces) to single spaces.
    collapsed = " ".join(text.split()).replace("\u00a0", " ")
    return collapsed or None


def normalize_number(raw: str | None) -> str | None:
    """Canonical numeric string ("1,200" -> "1200"; "12.50" -> "12.5").

    Canonical form strips redundant trailing zeros (same value, unambiguous).
    Returns None when the text is not unambiguously numeric ("1O5" -> None).
    """
    if raw is None:
        return None
    parsed = parse_number(raw)
    if parsed is None:
        return None
    return _canonical_decimal(parsed)


def _canonical_decimal(value: Decimal) -> str:
    if value == value.to_integral_value():
        return str(value.quantize(Decimal(1)))
    normalized = value.normalize()
    return format(normalized, "f")


def normalize_date(raw: str | None) -> str | None:
    """ISO-8601 date when the input is an unambiguous, documented format."""
    if raw is None:
        return None
    parsed = parse_date(raw)
    return parsed.isoformat() if parsed else None


def normalize_period(raw: str | None) -> str | None:
    """Period normalization: full dates -> ISO date; bare years and
    financial-year labels ("2025-26", "2025/26") preserved verbatim —
    their semantics are domain-specific and must not be guessed."""
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    if parse_date(text) is not None:
        return normalize_date(text)
    if len(text) == 4 and text.isdigit():
        year = int(text)
        if 1900 <= year <= 2200:
            return text  # bare year: kept, sanity-checked only
        return None
    # Financial-year style labels: kept verbatim (never interpreted as dates).
    if re.fullmatch(r"\d{4}[-/]\d{2}", text):
        return text
    return None


__all__ = [
    "normalize_text",
    "normalize_number",
    "normalize_date",
    "normalize_period",
    "normalize_decimal",
]


def normalize_decimal(value: Decimal | None) -> str | None:
    """Canonical string for an already-parsed Decimal (used by builders)."""
    if value is None:
        return None
    try:
        return _canonical_decimal(value)
    except InvalidOperation:
        return None
