"""Deterministic parsing helpers for validation.

`None` means "cannot be parsed" — the raw text is never altered and the
caller decides the outcome. No locale guessing, no fuzzy matching.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

# Explicitly supported date formats (documented; extend deliberately).
_DATE_FORMATS = (
    "%Y-%m-%d",  # ISO
    "%d/%m/%Y",  # DD/MM/YYYY (common in Indian reporting)
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y/%m/%d",
)


def parse_number(raw: str | None) -> Decimal | None:
    """Parse a numeric string, tolerating digit-group separators.

    Accepts: "1200", "1,200", "1,20,000" (Indian grouping), "-45.5", " 12 ".
    Returns None for anything else ("1O5", "12.3.4", "", None) — never guesses.
    """
    if raw is None:
        return None
    cleaned = raw.strip().replace(",", "").replace(" ", "")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_date(raw: str | None) -> date | None:
    """Parse a date string in the documented formats; None when impossible."""
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    from datetime import datetime

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None
