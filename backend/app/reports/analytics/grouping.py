"""Shared grouping/pooling helpers for the analytical layer (Step 12).

Grouping is deterministic (stable string ordering with NULLs last). Units
are part of every key: cross-unit reconciliation would require conversion
rules the platform does not have, and guessing one could fabricate values.
"""

from app.reports.engine import ConflictItem, RecordItem

# Deterministic ordering key: values sort naturally, None sorts last.
_ORDER_KEY = lambda value: (value is None, value or "")  # noqa: E731


def group_records(
    records: list[RecordItem],
) -> dict[tuple[str | None, str | None, str | None, str | None], list[RecordItem]]:
    """Group records by (entity, metric, period, unit) — the analytics key.

    Deterministic group iteration order: entity → metric → period → unit.
    """
    groups: dict[tuple[str | None, str | None, str | None, str | None], list[RecordItem]] = {}
    for record in records:
        key = (record.entity, record.metric, record.reporting_period, record.unit)
        groups.setdefault(key, []).append(record)
    return {
        key: groups[key]
        for key in sorted(
            groups,
            key=lambda k: (_ORDER_KEY(k[0]), _ORDER_KEY(k[1]), _ORDER_KEY(k[2]), _ORDER_KEY(k[3])),
        )
    }


def conflict_keys(conflicts: list[ConflictItem]) -> set[tuple[str | None, str | None, str | None, str | None]]:
    """The set of (entity, metric, period, unit) keys with detected conflicts."""
    return {
        (c.entity, c.metric, c.reporting_period, c.unit) for c in conflicts
    }
