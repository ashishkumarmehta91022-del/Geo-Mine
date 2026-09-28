"""Report analysis API integration tests — REQUIRE PostgreSQL (conftest
skip contract: these SKIP, never fake-pass, when the database is absent)."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.db


def _make_processed_document(migrated_engine, filename: str, rows: list[dict]) -> int:
    from app.models import Document, ExtractedRecord

    with Session(migrated_engine) as session:
        document = Document(
            filename=filename,
            document_type="xlsx",
            storage_reference=f"test/{filename}",
            status="processed",
            processed_at=datetime.now(timezone.utc),
        )
        session.add(document)
        session.flush()
        for row in rows:
            session.add(ExtractedRecord(document_id=document.id, **row))
        session.commit()
        return document.id


def _analyze(client, **overrides):
    body = {
        "title": "Integration Analytics",
        "report_type": "production",
        "reporting_period": "2025-06-30",
    }
    body.update(overrides)
    return client.post("/api/reports/analyze", json=body)


def test_analyze_returns_kpis_trends_and_charts(client, migrated_engine):
    _make_processed_document(
        migrated_engine, "a.xlsx",
        [
            dict(record_type="coal_production", entity_name="MINE_A",
                 metric_name="production", metric_value=1200, value_raw="1200",
                 normalized_value="1200", unit="tonnes",
                 reporting_period="2025-06-30", validation_status="valid"),
        ],
    )
    _make_processed_document(
        migrated_engine, "b.xlsx",
        [
            dict(record_type="coal_production", entity_name="MINE_B",
                 metric_name="production", metric_value=1350, value_raw="1350",
                 normalized_value="1350", unit="tonnes",
                 reporting_period="2025-06-30", validation_status="valid"),
        ],
    )
    response = _analyze(client)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["record_count"] == 2
    assert any(k["name"] == "total" for k in payload["kpis"])
    assert any(c["chart_type"] == "comparison" for c in payload["charts"])
    comparison = next(c for c in payload["comparisons"])
    assert comparison["absolute_difference"] == "150"


def test_analyze_propagates_conflicts_without_resolution(client, migrated_engine):
    _make_processed_document(
        migrated_engine, "conflict1.xlsx",
        [dict(record_type="coal_production", entity_name="MINE_X",
              metric_name="production", metric_value=1200, value_raw="1200",
              normalized_value="1200", unit="tonnes",
              reporting_period="2025-06-30", validation_status="valid")],
    )
    _make_processed_document(
        migrated_engine, "conflict2.xlsx",
        [dict(record_type="coal_production", entity_name="MINE_X",
              metric_name="production", metric_value=1350, value_raw="1350",
              normalized_value="1350", unit="tonnes",
              reporting_period="2025-06-30", validation_status="valid")],
    )
    payload = _analyze(client).json()
    assert payload["conflict_count"] == 1
    assert payload["excluded_value_count"] == 2
    assert any(k["name"] == "count_conflicts" and k["count"] == 1 for k in payload["kpis"])
    # No aggregate KPI over the conflicting values — no fake average/total.
    assert not any(
        k["name"] in ("total", "average") and k["value"] is not None
        for k in payload["kpis"]
    )
    assert any(i["kind"] == "CONFLICT" for i in payload["insights"])


def test_analyze_records_audit_row_metadata_only(client, migrated_engine):
    from app.models import AuditLog

    _make_processed_document(
        migrated_engine, "audit.xlsx",
        [dict(record_type="coal_production", entity_name="SECRET_ENTITY",
              metric_name="production", metric_value=1200, value_raw="1200",
              normalized_value="1200", unit="tonnes",
              reporting_period="2025-06-30", validation_status="valid")],
    )
    response = _analyze(client)
    assert response.status_code == 200
    with Session(migrated_engine) as session:
        rows = list(
            session.scalars(select(AuditLog).where(AuditLog.action == "report.analyze"))
        )
        assert len(rows) == 1
        details = rows[0].details or {}
        assert details["status"] == "ok"
        flat = str(details)
        assert "SECRET_ENTITY" not in flat and "1200" not in flat


def test_analyze_narrative_falls_back_without_llm(client, migrated_engine):
    _make_processed_document(
        migrated_engine, "narr.xlsx",
        [dict(record_type="coal_production", entity_name="MINE_A",
              metric_name="production", metric_value=1200, value_raw="1200",
              normalized_value="1200", unit="tonnes",
              reporting_period="2025-06-30", validation_status="valid")],
    )
    payload = _analyze(client, include_narrative=True).json()
    assert payload["narrative"] is not None
    assert payload["narrative"]["state"] == "deterministic"
    assert payload["narrative"]["ai_attempt"]["state"] == "unavailable"


def test_analyze_rejects_invalid_spec(client):
    response = _analyze(client, entities=["e"] * 51)
    assert response.status_code == 422
