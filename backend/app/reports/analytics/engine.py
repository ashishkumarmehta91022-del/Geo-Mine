"""Deterministic analytical engines (Step 12): KPI, trends, comparisons.

AUTHORITATIVE RULES (enforced everywhere in this module):
- Arithmetic uses ONLY stored normalized values that parse as finite numbers
  AND belong to records with a validated status (pass/valid). Everything else
  is excluded with an explicit reason — never silently converted.
- Records whose (entity, metric, period, unit) key has a detected conflict
  are excluded from arithmetic (reason: conflicting_values_not_averaged) —
  no fake averages, no winners, no definitive trends across conflicts.
- Where multiple records share one analytical cell, they must agree
  numerically or the cell is excluded (duplicate documents must not be
  summed into fabricated totals).
- Percentage change is computed only when mathematically valid (non-zero
  base). Differences are computed only within one unit.
- All outputs are deterministic and bounded.
"""

from collections import defaultdict
from decimal import Decimal
from typing import Any

from app.reports.analytics.grouping import conflict_keys, group_records
from app.reports.analytics.models import (
    AnalyticalStatus,
    Comparison,
    ComparisonSide,
    Distribution,
    ExcludedValue,
    KPI,
    Trend,
    TrendPoint,
)
from app.reports.analytics.numerics import (
    REASON_CONFLICT,
    REASON_NON_NUMERIC,
    REASON_VALIDATION_ERROR,
    parse_numeric,
)
from app.reports.engine import ConflictItem, RecordItem, ReportData

# Validation statuses whose values are trusted for arithmetic.
VALID_STATUSES = {"pass", "valid"}
# Statuses that always require review (never arithmetic-eligible).
REVIEW_STATUSES = {"warning", "error", "review_required"}

# Bounds (analytical input limits; deterministic caps).
MAX_AGGREGATION_GROUPS = 50
MAX_AGGREGATION_PERIODS = 24
MAX_AGGREGATE_KPIS = 400
MAX_TRENDS = 30
MAX_COMPARISONS = 20
MAX_DISTRIBUTIONS = 20

_PERIOD_EXCLUSION_REASONS = {
    "conflict": REASON_CONFLICT,
    "inconsistent": "inconsistent_values_within_period",
}


def _excluded(record: RecordItem, reason: str) -> ExcludedValue:
    return ExcludedValue(
        record_id=record.record_id,
        document_id=record.document_id,
        value_raw=record.value_raw,
        normalized_value=record.normalized_value,
        reason=reason,
    )


def _safe_values(
    records: list[RecordItem],
    conflicted: set[tuple[str | None, str | None, str | None, str | None]],
) -> tuple[list[tuple[RecordItem, Decimal]], list[ExcludedValue]]:
    """Split records into (safe numeric, excluded-with-reason).

    Exclusion reasons, in precedence order: conflict key > validation
    status > non-numeric/missing normalized value.
    """
    safe: list[tuple[RecordItem, Decimal]] = []
    excluded: list[ExcludedValue] = []
    for record in records:
        key = (record.entity, record.metric, record.reporting_period, record.unit)
        if key in conflicted:
            excluded.append(_excluded(record, REASON_CONFLICT))
            continue
        if (record.validation_status or "") not in VALID_STATUSES:
            excluded.append(_excluded(record, REASON_VALIDATION_ERROR))
            continue
        value = parse_numeric(record.normalized_value)
        if value is None:
            excluded.append(_excluded(record, REASON_NON_NUMERIC))
            continue
        safe.append((record, value))
    return safe, excluded


# --- Phase 3: KPI engine ----------------------------------------------------


def generate_kpis(data: ReportData) -> list[KPI]:
    """Deterministic KPI set: counts (always) + per-(metric, unit) aggregates.

    Count KPIs need no arithmetic and always appear. Aggregate KPIs
    (total/average/minimum/maximum) appear only for groups with at least one
    arithmetic-eligible value.
    """
    records = data.records
    conflicted = conflict_keys(data.conflicts)

    kpis: list[KPI] = []
    doc_ids = lambda rs: sorted({r.document_id for r in rs})  # noqa: E731

    def _count_kpi(name: str, label: str, count: int, rs: list[RecordItem]) -> KPI:
        return KPI(
            name=name, label=label, count=count, unit=None,
            source_record_ids=[r.record_id for r in rs][:500],
            source_document_ids=doc_ids(rs),
        )

    # --- count-style KPIs (no arithmetic, full population) ------------------
    kpis.append(_count_kpi("count_records", "Records in selection", len(records), records))
    validated = [r for r in records if (r.validation_status or "") in VALID_STATUSES]
    kpis.append(_count_kpi("count_validated", "Validated records", len(validated), validated))
    flagged = [r for r in records if (r.validation_status or "") in REVIEW_STATUSES]
    kpis.append(_count_kpi("count_requires_review", "Records requiring review", len(flagged), flagged))
    pending = [r for r in records if (r.validation_status or "") not in VALID_STATUSES | REVIEW_STATUSES]
    kpis.append(_count_kpi("count_pending_validation", "Records pending validation", len(pending), pending))
    missing = [r for r in records if not r.has_value()]
    kpis.append(_count_kpi("count_missing_values", "Records without a stored value", len(missing), missing))
    kpis.append(_count_kpi("count_conflicts", "Conflicting value groups", len(data.conflicts), []))

    # --- arithmetic KPIs per (metric, unit, period), conflict-aware ---------
    # Scope: ONE period at a time — summing across periods would fabricate a
    # meaningless domain figure. Within a period, records of the same entity
    # must agree numerically (duplicate documents of the same fact) or the
    # cell is excluded — never summed into inflated totals.
    by_group: dict[tuple[str | None, str | None],
                   dict[str | None, dict[str | None, list[tuple[RecordItem, Decimal]]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    excluded_by_group: dict[tuple[str | None, str | None], list[ExcludedValue]] = defaultdict(list)

    for record in records:
        group = (record.metric, record.unit)
        key = (record.entity, record.metric, record.reporting_period, record.unit)
        if key in conflicted:
            excluded_by_group[group].append(_excluded(record, REASON_CONFLICT))
            continue
        if (record.validation_status or "") not in VALID_STATUSES:
            excluded_by_group[group].append(_excluded(record, REASON_VALIDATION_ERROR))
            continue
        value = parse_numeric(record.normalized_value)
        if value is None:
            excluded_by_group[group].append(_excluded(record, REASON_NON_NUMERIC))
            continue
        by_group[group][record.reporting_period][record.entity].append((record, value))

    aggregate_budget = MAX_AGGREGATE_KPIS
    for (metric, unit) in sorted(
        by_group, key=lambda k: ((k[0] or "~"), (k[1] or "~"))
    )[:MAX_AGGREGATION_GROUPS]:
        if aggregate_budget <= 0:
            break
        periods = by_group[(metric, unit)]
        group_excluded = excluded_by_group.get((metric, unit), [])
        conflict_in_group = any(e.reason == REASON_CONFLICT for e in group_excluded)
        for period in sorted(
            periods, key=lambda p: (p is None, p or "")
        )[:MAX_AGGREGATION_PERIODS]:
            if aggregate_budget <= 0:
                break
            entity_map = periods[period]
            values: list[Decimal] = []
            ids: list[int] = []
            cell_exclusions: list[ExcludedValue] = []
            for entity in sorted(entity_map, key=lambda e: (e is None, e or "")):
                cell_value, _raw, cell_excl = _cell_value(entity_map[entity])
                cell_exclusions.extend(cell_excl)
                if cell_value is None:
                    continue
                values.append(cell_value)
                ids.extend(r.record_id for r, _ in entity_map[entity])
            if not values:
                continue
            aggregate_budget -= 4
            period_label = f" ({period})" if period else ""
            conflict_status = (
                AnalyticalStatus.REVIEW_REQUIRED.value
                if conflict_in_group or cell_exclusions
                else AnalyticalStatus.OK.value
            )
            common = dict(
                metric=metric, unit=unit, reporting_period=period,
                source_record_ids=ids[:500],
                source_document_ids=doc_ids([
                    r for rows in entity_map.values() for r, _ in rows
                ]),
                validation_status="pass",
                conflict_status=conflict_status,
                excluded=group_excluded + cell_exclusions,
            )
            kpis.append(KPI(name="total", label=f"Total {metric}{period_label}",
                            value=sum(values), **common))
            kpis.append(KPI(name="average", label=f"Average {metric}{period_label}",
                            value=sum(values) / Decimal(len(values)), **common))
            kpis.append(KPI(name="minimum", label=f"Minimum {metric}{period_label}",
                            value=min(values), **common))
            kpis.append(KPI(name="maximum", label=f"Maximum {metric}{period_label}",
                            value=max(values), **common))
    return kpis


# --- Phase 4 + 6: trend analysis ---------------------------------------------

_MONTHS = 12


def _period_sequence(first: str, last: str) -> list[str] | None:
    """Deterministic in-between periods when the format is calendar-like.

    Supports YYYY (yearly) and YYYY-MM (monthly). Returns None when the
    format is not recognized — gaps are then not inferable (documented
    limitation, never guessed).
    """
    import re

    if re.fullmatch(r"\d{4}", first) and re.fullmatch(r"\d{4}", last):
        start, end = int(first), int(last)
        if 0 < end - start <= 100:
            return [str(year) for year in range(start, end + 1)]
        return None
    pattern = r"\d{4}-\d{2}"
    if re.fullmatch(pattern, first) and re.fullmatch(pattern, last):
        start_y, start_m = int(first[:4]), int(first[5:7])
        end_y, end_m = int(last[:4]), int(last[5:7])
        if not (1 <= start_m <= _MONTHS and 1 <= end_m <= _MONTHS):
            return None
        months = (end_y - start_y) * _MONTHS + (end_m - start_m)
        if 0 < months <= 120:
            sequence = []
            year, month = start_y, start_m
            for _ in range(months + 1):
                sequence.append(f"{year:04d}-{month:02d}")
                month += 1
                if month > _MONTHS:
                    year, month = year + 1, 1
            return sequence
    return None


def _cell_value(
    cell: list[tuple[RecordItem, Decimal]],
) -> tuple[Decimal | None, str | None, list[ExcludedValue]]:
    """One analytical cell (same entity/metric/unit/period) → single value.

    Multiple records must agree numerically (duplicate documents of the same
    fact) — otherwise the cell is excluded rather than summed or averaged.
    """
    if not cell:
        return None, None, []
    if len(cell) == 1:
        record, value = cell[0]
        return value, record.value_raw, []
    values = {value for _, value in cell}
    if len(values) == 1:
        record = cell[0][0]
        return cell[0][1], record.value_raw, []
    return None, None, [
        ExcludedValue(
            record_id=r.record_id, document_id=r.document_id,
            value_raw=r.value_raw, normalized_value=r.normalized_value,
            reason=_PERIOD_EXCLUSION_REASONS["inconsistent"],
        )
        for r, _ in cell
    ]


def generate_trends(data: ReportData) -> list[Trend]:
    """Deterministic time-series per (entity, metric, unit) — conflict-aware."""
    records = data.records
    conflicted = conflict_keys(data.conflicts)

    by_series: dict[tuple[str | None, str | None, str | None],
                    dict[str | None, list[tuple[RecordItem, Decimal]]]] = defaultdict(lambda: defaultdict(list))
    excluded_by_series: dict[tuple[str | None, str | None, str | None], list[ExcludedValue]] = defaultdict(list)
    conflict_in_series: set[tuple[str | None, str | None, str | None]] = set()

    for record in records:
        series_key = (record.entity, record.metric, record.unit)
        cell_key = (record.entity, record.metric, record.reporting_period, record.unit)
        if cell_key in conflicted:
            conflict_in_series.add(series_key)
            excluded_by_series[series_key].append(_excluded(record, REASON_CONFLICT))
            continue
        if (record.validation_status or "") not in VALID_STATUSES:
            excluded_by_series[series_key].append(_excluded(record, REASON_VALIDATION_ERROR))
            continue
        value = parse_numeric(record.normalized_value)
        if value is None:
            excluded_by_series[series_key].append(_excluded(record, REASON_NON_NUMERIC))
            continue
        by_series[series_key][record.reporting_period].append((record, value))

    trends: list[Trend] = []
    for series_key in sorted(by_series, key=lambda k: ((k[0] or "~"), (k[1] or "~"), (k[2] or "~")))[:MAX_TRENDS]:
        entity, metric, unit = series_key
        cells = by_series[series_key]
        excluded = excluded_by_series[series_key]
        ordered_periods = sorted(
            (p for p in cells if p is not None),
            key=lambda p: (p is None, p or ""),
        )
        points: list[TrendPoint] = []
        cell_exclusions: list[ExcludedValue] = []
        for period in ordered_periods:
            value, value_raw, exclusions = _cell_value(cells[period])
            cell_exclusions.extend(exclusions)
            if value is None:
                continue
            record_ids = [r.record_id for r, _ in cells[period]]
            document_ids = sorted({r.document_id for r, _ in cells[period]})
            validation = cells[period][0][0].validation_status
            points.append(TrendPoint(
                period=period, value=value, value_raw=value_raw,
                record_ids=record_ids, document_ids=document_ids,
                validation_status=validation,
            ))
        excluded.extend(cell_exclusions)

        # Explicit gap representation — only for calendar-like period formats.
        missing: list[str] = []
        if len(points) >= 2:
            sequence = _period_sequence(points[0].period, points[-1].period)
            if sequence is not None:
                present = {p.period for p in points}
                missing = [p for p in sequence if p not in present]

        first = points[0].value if points else None
        last = points[-1].value if points else None
        absolute = (last - first) if (first is not None and last is not None and len(points) >= 2) else None
        percent: Decimal | None = None
        percent_valid = False
        if absolute is not None and first is not None and first != 0:
            percent = (absolute / first) * Decimal(100)
            percent_valid = True
        direction = "unchanged"
        if absolute is not None and absolute > 0:
            direction = "increasing"
        elif absolute is not None and absolute < 0:
            direction = "decreasing"

        trends.append(Trend(
            entity=entity, metric=metric, unit=unit,
            points=points, missing_periods=missing,
            first_value=first, last_value=last,
            absolute_change=absolute, percent_change=percent,
            percent_change_valid=percent_valid, direction=direction,
            status=(
                AnalyticalStatus.REVIEW_REQUIRED.value
                if series_key in conflict_in_series or excluded
                else AnalyticalStatus.OK.value
            ),
            source_record_ids=[rid for p in points for rid in p.record_ids],
            source_document_ids=sorted({did for p in points for did in p.document_ids}),
            excluded=excluded,
        ))
    return trends


# --- Phase 5 + 6: comparison analysis ----------------------------------------


def generate_comparisons(data: ReportData) -> list[Comparison]:
    """Deterministic comparisons across entities (per metric/unit/period).

    Differences are computed only within one unit; entities without a safe
    value stay listed (raw preserved) and invalidate the difference. No
    "better/worse" labels — numerical difference only.
    """
    records = data.records
    conflicted = conflict_keys(data.conflicts)

    by_cell: dict[tuple[str | None, str | None, str | None, str | None],
                  dict[str | None, list[tuple[RecordItem, Decimal]]]] = defaultdict(lambda: defaultdict(list))
    known_entities: dict[tuple[str | None, str | None, str | None, str | None], set[str | None]] = defaultdict(set)
    excluded_by_cell: dict[tuple[str | None, str | None, str | None, str | None], list[ExcludedValue]] = defaultdict(list)
    conflict_in_cell: set[tuple[str | None, str | None, str | None, str | None]] = set()

    for record in records:
        cell = (record.metric, record.unit, record.reporting_period, None)
        key = (record.entity, record.metric, record.reporting_period, record.unit)
        if key in conflicted:
            conflict_in_cell.add(cell)
            excluded_by_cell[cell].append(_excluded(record, REASON_CONFLICT))
            known_entities[cell].add(record.entity)
            continue
        if (record.validation_status or "") not in VALID_STATUSES:
            excluded_by_cell[cell].append(_excluded(record, REASON_VALIDATION_ERROR))
            known_entities[cell].add(record.entity)
            continue
        value = parse_numeric(record.normalized_value)
        if value is None:
            excluded_by_cell[cell].append(_excluded(record, REASON_NON_NUMERIC))
            known_entities[cell].add(record.entity)
            continue
        by_cell[cell][record.entity].append((record, value))

    comparisons: list[Comparison] = []
    for cell in sorted(by_cell | {c: {} for c in known_entities}, key=lambda k: ((k[0] or "~"), (k[1] or "~"), (k[2] or "~")))[:MAX_COMPARISONS]:
        metric, unit, period, _ = cell
        entity_map = by_cell.get(cell, {})
        all_entities = known_entities.get(cell, set()) | set(entity_map)
        sides: list[ComparisonSide] = []
        excluded = list(excluded_by_cell[cell])
        for entity in sorted((e for e in all_entities if e is not None), key=lambda e: (e is None, e or "")):
            entity_rows = entity_map.get(entity, [])
            value, value_raw, cell_excl = _cell_value(entity_rows)
            excluded.extend(cell_excl)
            sides.append(ComparisonSide(
                label=entity or "?", value=value, value_raw=value_raw, unit=unit,
                record_ids=[r.record_id for r, _ in entity_rows],
                document_ids=sorted({r.document_id for r, _ in entity_rows}),
                validation_status=entity_rows[0][0].validation_status if entity_rows else None,
            ))

        # A comparison needs at least two distinct entities — a single side
        # is an aggregate, not a comparison (suppressed, not fabricated).
        if len({s.label for s in sides}) < 2:
            continue
        valued = [s.value for s in sides if s.value is not None]
        difference = (max(valued) - min(valued)) if len(valued) >= 2 else None
        comparisons.append(Comparison(
            kind="entities", metric=metric, unit=unit, period=period,
            sides=sides, absolute_difference=difference,
            difference_unit=unit if difference is not None else None,
            difference_valid=difference is not None,
            status=(
                AnalyticalStatus.REVIEW_REQUIRED.value
                if cell in conflict_in_cell or excluded
                else AnalyticalStatus.OK.value
            ),
            source_record_ids=[rid for s in sides for rid in s.record_ids],
            source_document_ids=sorted({did for s in sides for did in s.document_ids}),
            excluded=excluded,
        ))
    return comparisons


def collect_exclusions(data: ReportData) -> list[ExcludedValue]:
    """Single authoritative derivation of ALL records excluded from arithmetic.

    Classification per record (deterministic precedence): conflict key >
    validation status > non-numeric normalized value > disagreeing cell.
    Used for the top-level excluded_values payload so exclusions are complete
    even when a whole group produces no aggregate KPI.
    """
    records = data.records
    conflicted = conflict_keys(data.conflicts)
    excluded: list[ExcludedValue] = []
    eligible_by_cell: dict[tuple[str | None, str | None, str | None, str | None],
                           list[tuple[RecordItem, Decimal]]] = defaultdict(list)
    for record in records:
        key = (record.entity, record.metric, record.reporting_period, record.unit)
        if key in conflicted:
            excluded.append(_excluded(record, REASON_CONFLICT))
            continue
        if (record.validation_status or "") not in VALID_STATUSES:
            excluded.append(_excluded(record, REASON_VALIDATION_ERROR))
            continue
        value = parse_numeric(record.normalized_value)
        if value is None:
            excluded.append(_excluded(record, REASON_NON_NUMERIC))
            continue
        eligible_by_cell[key].append((record, value))
    for cell in eligible_by_cell:
        values = {value for _, value in eligible_by_cell[cell]}
        if len(values) > 1:  # disagreeing duplicates — excluded, not averaged
            excluded.extend(
                ExcludedValue(
                    record_id=r.record_id, document_id=r.document_id,
                    value_raw=r.value_raw, normalized_value=r.normalized_value,
                    reason=_PERIOD_EXCLUSION_REASONS["inconsistent"],
                )
                for r, _ in eligible_by_cell[cell]
            )
    return sorted(
        {(e.record_id, e.reason): e for e in excluded}.values(),
        key=lambda e: (e.record_id, e.reason),
    )


# --- Distribution (Phase 2 object, deterministic histogram) -------------------


def generate_distributions(data: ReportData) -> list[Distribution]:
    """Histogram of safe numeric values per (metric, unit) — 5 equal bins."""
    records = data.records
    conflicted = conflict_keys(data.conflicts)

    by_metric_unit: dict[tuple[str | None, str | None], list[tuple[RecordItem, Decimal]]] = defaultdict(list)
    excluded_all: dict[tuple[str | None, str | None], list[ExcludedValue]] = defaultdict(list)
    for record in records:
        key = (record.metric, record.unit)
        cell_key = (record.entity, record.metric, record.reporting_period, record.unit)
        if cell_key in conflicted:
            excluded_all[key].append(_excluded(record, REASON_CONFLICT))
            continue
        if (record.validation_status or "") not in VALID_STATUSES:
            excluded_all[key].append(_excluded(record, REASON_VALIDATION_ERROR))
            continue
        value = parse_numeric(record.normalized_value)
        if value is None:
            excluded_all[key].append(_excluded(record, REASON_NON_NUMERIC))
            continue
        by_metric_unit[key].append((record, value))

    distributions: list[Distribution] = []
    for key in sorted(by_metric_unit, key=lambda k: ((k[0] or "~"), (k[1] or "~")))[:MAX_DISTRIBUTIONS]:
        metric, unit = key
        entries = by_metric_unit[key]
        values = [value for _, value in entries]
        low, high = min(values), max(values)
        bins: list[dict[str, Any]] = []
        if low == high:
            bins.append({"range": f"[{low}, {low}]", "count": len(values)})
        else:
            width = (high - low) / Decimal(5)
            for index in range(5):
                bin_low = low + width * index
                bin_high = bin_low + width if index < 4 else high
                count = sum(
                    1 for value in values
                    if (bin_low <= value < bin_high) or (index == 4 and value == bin_high)
                )
                bins.append({"range": f"[{bin_low}, {bin_high}]", "count": count})
        distributions.append(Distribution(
            metric=metric, unit=unit, bins=bins, total_counted=len(values),
            excluded=excluded_all[key],
        ))
    return distributions
