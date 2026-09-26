"""Deterministic validation rules — each independently testable and extensible.

Every rule returns RuleOutcomes only; nothing here mutates candidate values.
Rule codes are stable identifiers surfaced in the API and review queue.
"""

from datetime import date
from decimal import Decimal

from app.constants import ValidationSeverity, ValidationStatus
from app.validation.config import DateSpec, NumericSpec, RangeSpec, ValidationConfig
from app.validation.models import (
    FIELD_VALUE,
    RuleOutcome,
    ValueCandidate,
)
from app.validation.parsing import parse_date, parse_number

# --- rule codes (stable identifiers) -------------------------------------------

REQUIRED_FIELD_MISSING = "REQUIRED_FIELD_MISSING"
NUMERIC_FORMAT = "NUMERIC_FORMAT"
NUMERIC_NEGATIVE = "NUMERIC_NEGATIVE"
NUMERIC_INTEGER_EXPECTED = "NUMERIC_INTEGER_EXPECTED"
RANGE_OUT_OF_BOUNDS = "RANGE_OUT_OF_BOUNDS"
DATE_INVALID = "DATE_INVALID"
DATE_FUTURE = "DATE_FUTURE"
OCR_LOW_CONFIDENCE = "OCR_LOW_CONFIDENCE"
OCR_REVIEW_FLAGGED = "OCR_REVIEW_FLAGGED"
DUPLICATE_DETECTED = "DUPLICATE_DETECTED"
CROSS_DOCUMENT_CONFLICT = "CROSS_DOCUMENT_CONFLICT"


class ValidationRule:
    """Base class: validate(candidates, config) -> list[RuleOutcome]."""

    rule_code: str = ""

    def validate(self, candidates: list[ValueCandidate], config: ValidationConfig) -> list[RuleOutcome]:
        raise NotImplementedError


# --- 1. Required field --------------------------------------------------------------


class RequiredFieldRule(ValidationRule):
    """Missing configured required fields generate results, never defaults."""

    rule_code = REQUIRED_FIELD_MISSING

    def validate(self, candidates, config):
        outcomes: list[RuleOutcome] = []
        severities = config.required_fields
        for candidate in candidates:
            for field_name, severity in severities.items():
                value = candidate.field_value(field_name)
                if value is None or str(value).strip() == "":
                    outcomes.append(
                        RuleOutcome(
                            rule_code=self.rule_code,
                            status=ValidationStatus.ERROR,
                            severity=severity,
                            message=f"Required field '{field_name}' is missing.",
                            candidate=candidate,
                            expected=f"non-empty {field_name}",
                        )
                    )
        return outcomes


# --- 2. Numeric -----------------------------------------------------------------------


class NumericRule(ValidationRule):
    """Deterministic numeric checks: parseability, negatives, integer expectations."""

    rule_code = NUMERIC_FORMAT

    def validate(self, candidates, config):
        outcomes: list[RuleOutcome] = []
        specs = config.numeric_fields
        for candidate in candidates:
            for field_name, spec in specs.items():
                raw = candidate.field_value(field_name)
                if raw is None or str(raw).strip() == "":
                    continue  # missing values are the required-field rule's job
                parsed = parse_number(str(raw))
                if parsed is None:
                    outcomes.append(
                        RuleOutcome(
                            rule_code=NUMERIC_FORMAT,
                            status=ValidationStatus.ERROR,
                            severity=ValidationSeverity.ERROR,
                            message=(
                                f"Field '{field_name}' value '{raw}' is not a valid number "
                                "(kept verbatim; no correction attempted)."
                            ),
                            candidate=candidate,
                            expected="numeric format",
                            details={"raw": raw},
                        )
                    )
                    continue
                if parsed < 0 and not spec.allow_negative:
                    outcomes.append(
                        RuleOutcome(
                            rule_code=NUMERIC_NEGATIVE,
                            status=ValidationStatus.ERROR,
                            severity=ValidationSeverity.ERROR,
                            message=f"Field '{field_name}' value {parsed} is negative; negatives are not allowed for this field.",
                            candidate=candidate,
                            expected=">= 0",
                            details={"parsed": str(parsed)},
                        )
                    )
                if spec.integer_only and parsed != parsed.to_integral_value():
                    outcomes.append(
                        RuleOutcome(
                            rule_code=NUMERIC_INTEGER_EXPECTED,
                            status=ValidationStatus.WARNING,
                            severity=ValidationSeverity.WARNING,
                            message=f"Field '{field_name}' value {parsed} has decimals where an integer is expected.",
                            candidate=candidate,
                            expected="integer",
                            details={"parsed": str(parsed)},
                        )
                    )
        return outcomes


# --- 3. Range ----------------------------------------------------------------------------


class RangeRule(ValidationRule):
    """Configured bounds; status (error|warning) comes from the rule config."""

    rule_code = RANGE_OUT_OF_BOUNDS

    def validate(self, candidates, config):
        outcomes: list[RuleOutcome] = []
        for candidate in candidates:
            for field_name, spec in config.ranges.items():
                raw = candidate.field_value(field_name)
                parsed = parse_number(str(raw)) if raw is not None else None
                if parsed is None:
                    continue  # unparseable handled by NumericRule
                inside = (
                    spec.minimum <= parsed <= spec.maximum
                    if spec.inclusive
                    else spec.minimum < parsed < spec.maximum
                )
                if inside:
                    continue
                status = (
                    ValidationStatus.ERROR
                    if spec.status == "error"
                    else ValidationStatus.WARNING
                )
                outcomes.append(
                    RuleOutcome(
                        rule_code=RANGE_OUT_OF_BOUNDS,
                        status=status,
                        severity=ValidationSeverity.ERROR if status == ValidationStatus.ERROR else ValidationSeverity.WARNING,
                        message=(
                            f"Field '{field_name}' value {parsed} is outside the configured "
                            f"{'inclusive' if spec.inclusive else 'exclusive'} range "
                            f"[{spec.minimum}, {spec.maximum}]."
                        ),
                        candidate=candidate,
                        expected=f"[{spec.minimum}, {spec.maximum}]",
                        details={"parsed": str(parsed), "config_status": spec.status},
                    )
                )
        return outcomes


# --- 4. Date -------------------------------------------------------------------------------


class DateRule(ValidationRule):
    """Format/impossible-date checks + configured future-date prohibition."""

    rule_code = DATE_INVALID

    def validate(self, candidates, config):
        outcomes: list[RuleOutcome] = []
        for candidate in candidates:
            for field_name, spec in config.date_fields.items():
                raw = candidate.field_value(field_name)
                if raw is None or str(raw).strip() == "":
                    continue
                parsed = parse_date(str(raw))
                if parsed is None:
                    outcomes.append(
                        RuleOutcome(
                            rule_code=DATE_INVALID,
                            status=ValidationStatus.WARNING,
                            severity=ValidationSeverity.INFO,
                            message=(
                                f"Field '{field_name}' value '{raw}' is not a recognized date format "
                                "(e.g. 2025-06-30, 30/06/2025). Kept verbatim."
                            ),
                            candidate=candidate,
                            expected="date in documented formats",
                            details={"raw": raw},
                        )
                    )
                    continue
                if not spec.allow_future and parsed > date.today():
                    outcomes.append(
                        RuleOutcome(
                            rule_code=DATE_FUTURE,
                            status=ValidationStatus.WARNING,
                            severity=ValidationSeverity.WARNING,
                            message=f"Field '{field_name}' date {parsed.isoformat()} is in the future.",
                            candidate=candidate,
                            expected=f"<= {date.today().isoformat()}",
                            details={"parsed": parsed.isoformat()},
                        )
                    )
        return outcomes


# --- 5. OCR confidence ------------------------------------------------------------------------


class OCRConfidenceRule(ValidationRule):
    """Low-confidence OCR values enter human review — text never altered."""

    rule_code = OCR_LOW_CONFIDENCE

    def validate(self, candidates, config):
        outcomes: list[RuleOutcome] = []
        for candidate in candidates:
            if candidate.review_required or (
                candidate.confidence is not None
                and candidate.confidence < config.ocr_confidence_threshold
            ):
                outcomes.append(
                    RuleOutcome(
                        rule_code=(
                            OCR_REVIEW_FLAGGED
                            if candidate.review_required and candidate.confidence is None
                            else OCR_LOW_CONFIDENCE
                        ),
                        status=ValidationStatus.REVIEW_REQUIRED,
                        severity=ValidationSeverity.WARNING,
                        message=(
                            "OCR confidence below threshold or review flagged upstream; "
                            "value preserved verbatim for human inspection."
                        ),
                        candidate=candidate,
                        expected=f"confidence >= {config.ocr_confidence_threshold}",
                        details={
                            "confidence": float(candidate.confidence) if candidate.confidence is not None else None,
                            "ocr": candidate.ocr_metadata,
                        },
                    )
                )
        return outcomes


# --- 6. Duplicates --------------------------------------------------------------------------------


class DuplicateRule(ValidationRule):
    """Configured duplicate key → WARNING; duplicates are flagged, never deleted.

    The key is DEMO/configured — NOT claimed as an official CMPDI/CIL key.
    """

    rule_code = DUPLICATE_DETECTED

    def validate(self, candidates, config):
        outcomes: list[RuleOutcome] = []
        key_fields = config.duplicate_key_fields
        seen: dict[tuple, ValueCandidate] = {}
        for candidate in candidates:
            key = tuple(
                (candidate.field_value(f) or "").strip().lower() for f in key_fields
            )
            if key in seen:
                first = seen[key]
                outcomes.append(
                    RuleOutcome(
                        rule_code=self.rule_code,
                        status=ValidationStatus.WARNING,
                        severity=ValidationSeverity.WARNING,
                        message=(
                            f"Duplicate key {list(key_fields)} matches document "
                            f"#{first.document_id} (record #{first.record_id}); flagged, not deleted."
                        ),
                        candidate=candidate,
                        details={
                            "key_fields": list(key_fields),
                            "key": list(key),
                            "first_document_id": first.document_id,
                            "first_record_id": first.record_id,
                        },
                    )
                )
            else:
                seen[key] = candidate
        return outcomes


# --- 7. Cross-document consistency ------------------------------------------------------------------


class CrossDocumentConsistencyRule(ValidationRule):
    """Same consistency key with different values → conflict; both sources kept.

    Never picks a winner — that decision belongs to a human reviewer.
    """

    rule_code = CROSS_DOCUMENT_CONFLICT

    def validate(self, candidates, config):
        outcomes: "list[RuleOutcome]" = []
        key_fields = config.consistency_key_fields
        groups: dict[tuple, list[ValueCandidate]] = {}
        for candidate in candidates:
            key = tuple(
                (candidate.field_value(f) or "").strip().lower() for f in key_fields
            )
            groups.setdefault(key, []).append(candidate)

        for key, group in groups.items():
            numeric_members = [c for c in group if c.numeric_value is not None]
            distinct = {
                float(c.numeric_value) for c in numeric_members
            }
            if len(distinct) < 2:
                continue

            # Deterministic ordering: by document_id, then record id.
            ordered = sorted(numeric_members, key=lambda c: (c.document_id, c.record_id or 0))
            anchor = ordered[0]
            for other in ordered[1:]:
                outcomes.append(
                    RuleOutcome(
                        rule_code=self.rule_code,
                        status=ValidationStatus.REVIEW_REQUIRED,
                        severity=ValidationSeverity.WARNING,
                        message=(
                            f"Conflicting values for {list(key_fields)}={list(key)}: "
                            f"document #{anchor.document_id} → {anchor.numeric_value} vs "
                            f"document #{other.document_id} → {other.numeric_value}. "
                            "No winner selected; human review required."
                        ),
                        candidate=anchor,
                        details={
                            "key_fields": list(key_fields),
                            "key": list(key),
                            "values": [
                                {
                                    "document_id": c.document_id,
                                    "record_id": c.record_id,
                                    "source_reference": c.source_reference,
                                    "value": str(c.numeric_value),
                                    "document_filename": c.document_filename,
                                }
                                for c in (anchor, other)
                            ],
                        },
                    )
                )
        return outcomes


# --- registry ------------------------------------------------------------------------------------------

DEFAULT_RULES: tuple[ValidationRule, ...] = (
    RequiredFieldRule(),
    NumericRule(),
    RangeRule(),
    DateRule(),
    OCRConfidenceRule(),
    DuplicateRule(),
    CrossDocumentConsistencyRule(),
)
