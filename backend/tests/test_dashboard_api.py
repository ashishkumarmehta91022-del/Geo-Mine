"""Step 14 dashboard API integration tests — REQUIRE PostgreSQL (conftest
skip contract: SKIP, never fake-pass, when the database is absent)."""

import pytest

pytestmark = pytest.mark.db


def _add_document(migrated_engine, filename: str, status: str = "processed",
                  validation_status: str | None = "pass",
                  records: int = 0) -> int:
    from datetime import datetime, timezone

    from sqlalchemy.orm import Session

    from app.models import Document, ExtractedRecord

    with Session(migrated_engine) as session:
        document = Document(
            filename=filename,
            document_type="pdf",
            storage_reference=f"test/{filename}",
            status=status,
            processed_at=datetime.now(timezone.utc) if status == "processed" else None,
            uploaded_at=datetime.now(timezone.utc),
            validation_status=validation_status,
            extraction_status="completed" if status == "processed" else None,
        )
        session.add(document)
        session.flush()
        for index in range(records):
            session.add(ExtractedRecord(
                document_id=document.id,
                record_type="coal_production",
                entity_name="DASHBOARD_MINE",
                metric_name="production",
                metric_value=100,
                value_raw="100",
                normalized_value="100",
                unit="tonnes",
                reporting_period="2025-06-30",
                validation_status="pass",
            ))
        session.commit()
        return document.id


def test_summary_reports_live_counts(client, migrated_engine):
    _add_document(migrated_engine, "live1.pdf", status="processed", records=2)
    _add_document(migrated_engine, "live2.pdf", status="uploaded", records=0,
                  validation_status=None)
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data_available"] is True
    assert payload["documents"]["total"] == 2
    assert payload["documents"]["processed"] == 1
    assert payload["records"]["total"] == 2
    assert payload["database"]["status"] == "CONNECTED"
    assert len(payload["recent_documents"]) == 2
    recent = payload["recent_documents"][0]
    assert {"document_id", "filename", "status", "record_count"} <= set(recent)


def test_summary_empty_database_is_true_zeroes(client, migrated_engine):
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data_available"] is True
    assert payload["documents"]["total"] == 0
    assert payload["records"]["total"] == 0
    assert payload["validation"]["total"] == 0
    assert payload["intelligence"]["available"] is False
    assert "No indexed documents" in payload["intelligence"]["detail"]


def test_summary_intelligence_available_with_indexed_content(client, migrated_engine):
    from datetime import datetime, timezone

    from sqlalchemy.orm import Session

    from app.models import Document, DocumentPage
    from app.services import knowledge_service

    document_id = _add_document(migrated_engine, "intel.pdf", records=0)
    with Session(migrated_engine) as session:
        session.add(DocumentPage(
            document_id=document_id, page_number=1, content_type="page",
            extracted_text="Coal production output tonnes. Coal production review.",
            extraction_status="extracted", processing_status="completed",
        ))
        session.commit()
    knowledge_service.index_document(Session(migrated_engine), document_id)
    payload = client.get("/api/dashboard/summary").json()
    assert payload["intelligence"]["available"] is True
    assert payload["intelligence"]["indexed_documents"] == 1
    assert payload["intelligence"]["topic_count"] >= 1
    assert any("coal" in t["label"].lower() or "coal" in str(t).lower()
               for t in payload["intelligence"]["top_topics"] + payload["intelligence"]["top_terms"])


def test_summary_writes_metadata_only_audit_row(client, migrated_engine):
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.models import AuditLog

    _add_document(migrated_engine, "auditcheck.pdf")
    client.get("/api/dashboard/summary")
    with Session(migrated_engine) as session:
        rows = list(session.scalars(
            select(AuditLog).where(AuditLog.action == "dashboard.summary")
        ))
        assert len(rows) == 1
        details = rows[0].details or {}
        assert details["data_available"] is True
        flat = str(details)
        assert "auditcheck" not in flat and "DASHBOARD_MINE" not in flat
