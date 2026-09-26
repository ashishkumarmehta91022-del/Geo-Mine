"""Validation rule configuration.

*** DEMONSTRATION RULES ***
The defaults below exist to exercise the engine. They are NOT authoritative
CMPDI/CIL business rules — real ranges/keys must come from project
requirements and be supplied via configuration (environment/service layer),
not invented here. Every rule reads its parameters from this config, so
swapping in authoritative values requires no code changes.
"""

from dataclasses import dataclass, field

from app.config import settings
from app.validation.models import FIELD_ENTITY, FIELD_PERIOD, FIELD_VALUE


@dataclass(frozen=True)
class NumericSpec:
    allow_negative: bool = False
    integer_only: bool = False


@dataclass(frozen=True)
class RangeSpec:
    minimum: float
    maximum: float
    inclusive: bool = True
    # Status applied when outside the range (error | warning per config).
    status: str = "error"


@dataclass(frozen=True)
class DateSpec:
    allow_future: bool = False


@dataclass(frozen=True)
class ValidationConfig:
    """All rule parameters in one deterministic, swappable object."""

    # field name -> severity if missing entirely
    required_fields: dict[str, str] = field(default_factory=dict)
    # field name -> numeric expectations
    numeric_fields: dict[str, NumericSpec] = field(default_factory=dict)
    # field name -> acceptable range
    ranges: dict[str, RangeSpec] = field(default_factory=dict)
    # field name -> date expectations
    date_fields: dict[str, DateSpec] = field(default_factory=dict)
    # duplicate-detection key (DEMO key — not an official CMPDI/CIL unique key)
    duplicate_key_fields: tuple[str, ...] = (FIELD_ENTITY, FIELD_PERIOD)
    # cross-document consistency key (DEMO)
    consistency_key_fields: tuple[str, ...] = (FIELD_ENTITY, FIELD_PERIOD)
    # OCR confidences below this become review_required (from Step 5 settings)
    ocr_confidence_threshold: float = settings.ocr_confidence_threshold


def demo_config() -> ValidationConfig:
    """DEMO configuration — clearly-labelled sample rules for development.

    LABEL: demonstration only. Uses generic DEMO bounds (e.g. production
    quantity 0..10,000,000) that MUST be replaced by authoritative limits.
    """
    return ValidationConfig(
        required_fields={
            FIELD_ENTITY: "error",  # which mine/entity
            FIELD_PERIOD: "warning",  # which period (demo: warning severity)
        },
        numeric_fields={
            FIELD_VALUE: NumericSpec(allow_negative=False, integer_only=False),
        },
        ranges={
            # DEMO range for any numeric metric value — NOT an official limit.
            FIELD_VALUE: RangeSpec(minimum=0, maximum=10_000_000, inclusive=True, status="error"),
        },
        date_fields={
            FIELD_PERIOD: DateSpec(allow_future=False),
        },
        duplicate_key_fields=(FIELD_ENTITY, FIELD_PERIOD),
        consistency_key_fields=(FIELD_ENTITY, FIELD_PERIOD),
        ocr_confidence_threshold=settings.ocr_confidence_threshold,
    )
