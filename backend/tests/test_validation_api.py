"""Validation API integration tests — REQUIRE PostgreSQL (conftest.py skip contract)."""

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.db


def _make_document_with_records(migrated_engine, filename: str, rows: list[dict]) -> int:
    """Insert a document + extracted records directly (validation input data)."""
    from datetime import datetime, timezone

    from sqlalchemy.orm import Session

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


def _run(client, document_id: int):
    return client.post(f"/api/validation/run/{document_id}")


# --- successful runs ------------------------------------------------------------------


def test_validation_run_summary_and_persistence(client, migrated_engine):
    document_id = _make_document_with_records(
        migrated_engine,
        "prod_a.xlsx",
        [
            dict(
                record_type="coal_production",
                entity_name="DEMO_MINE_A",
                metric_name="DEMO_COAL_PRODUCTION",
                metric_value=1200,
                unit="tonnes",
                reporting_period="2025-06-30",
                source_reference="sheet Production, row 2",
            )
        ],
    )

    response = _run(client, document_id)
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["document_id"] == document_id
    assert summary["total_checks"] >= 0
    assert "review_required" in summary

    # Results persisted with provenance.
    with migrated_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT document_id, rule_code, status, original_value FROM validation_results "
                "WHERE document_id = :id"
            ),
            {"id": document_id},
        ).all()
    assert all(row[0] == document_id for row in rows)


def test_missing_required_field_creates_result_and_marks_record(client, migrated_engine):
    document_id = _make_document_with_records(
        migrated_engine,
        "prod_missing.xlsx",
        [
            dict(
                record_type="coal_production",
                entity_name="DEMO_MINE_A",
                metric_name="DEMO_COAL_PRODUCTION",
                metric_value=1200,
                reporting_period=None,  # demo-required field missing
            )
        ],
    )
    summary = _run(client, document_id).json()
    # Missing period → REQUIRED_FIELD_MISSING with status=ERROR (the rule's
    # severity is 'warning' — how loud — while the outcome status is error).
    assert summary["errors"] >= 1

    stored = client.get(f"/api/validation/{document_id}").json()
    assert stored["summary"]["total_checks"] == summary["total_checks"]
    assert any(item["rule_code"] == "REQUIRED_FIELD_MISSING" for item in stored["items"])


def test_original_value_preserved_and_record_rolled_up(client, migrated_engine):
    """A rule violation flags the record but NEVER rewrites its value."""
    document_id = _make_document_with_records(
        migrated_engine,
        "prod_negative.xlsx",
        [
            dict(
                record_type="coal_production",
                entity_name="DEMO_MINE_A",
                metric_name="DEMO_COAL_PRODUCTION",
                metric_value=-50,  # demo rule: negatives not allowed
                reporting_period="2025-06-30",
            )
        ],
    )
    _run(client, document_id)

    with migrated_engine.connect() as conn:
        value, validation_status = conn.execute(
            text("SELECT metric_value, validation_status FROM extracted_records WHERE document_id = :id"),
            {"id": document_id},
        ).one()
    assert value == -50  # untouched
    assert validation_status == "failed"  # flagged, not corrected


# --- OCR confidence → review queue ---------------------------------------------------------


def test_ocr_low_confidence_page_enters_review_queue(client, migrated_engine):
    from datetime import datetime, timezone

    from sqlalchemy.orm import Session

    from app.models import Document, DocumentPage

    with Session(migrated_engine) as session:
        document = Document(
            filename="scan_lowconf.pdf",
            document_type="pdf",
            storage_reference="test/scan_lowconf.pdf",
            status="processed",
            processed_at=datetime.now(timezone.utc),
        )
        session.add(document)
        session.flush()
        session.add(
            DocumentPage(
                document_id=document.id,
                page_number=2,
                content_type="page",
                section_reference="page 2",
                extracted_text="1O5",  # verbatim uncertain OCR text
                extraction_status="ocr_extracted",
                structured_metadata={
                    "ocr": {
                        "engine": "rapidocr-onnxruntime",
                        "engine_version": "1.2.3",
                        "confidence": 0.42,
                        "review_required": True,
                        "low_confidence_count": 1,
                        "bounding_boxes": [
                            {"text": "1O5", "x1": 0, "y1": 0, "x2": 50, "y2": 20, "confidence": 0.42}
                        ],
                    }
                },
            )
        )
        session.commit()
        document_id = document.id

    summary = _run(client, document_id).json()
    assert summary["review_required"] >= 1

    queue = client.get("/api/validation/review-queue").json()
    assert queue["total"] >= 1
    item = next(i for i in queue["items"] if i["document_id"] == document_id)
    assert item["rule_code"] in {"OCR_LOW_CONFIDENCE", "OCR_REVIEW_FLAGGED"}
    assert item["status"] == "review_required"
    assert item["confidence"] == 0.42
    assert item["original_value"] == "1O5"  # OCR text preserved for the reviewer
    assert item["source_reference"] == "page 2"


# --- cross-document conflicts -----------------------------------------------------------------


def test_cross_document_conflict_flags_review_and_preserves_both(client, migrated_engine):
    doc_a = _make_document_with_records(
        migrated_engine,
        "conflict_a.xlsx",
        [
            dict(
                record_type="coal_production",
                entity_name="DEMO_MINE_A",
                metric_name="DEMO_COAL_PRODUCTION",
                metric_value=1200,
                reporting_period="2025-06-30",
                source_reference="sheet Production, row 2",
            )
        ],
    )
    doc_b = _make_document_with_records(
        migrated_engine,
        "conflict_b.xlsx",
        [
            dict(
                record_type="coal_production",
                entity_name="DEMO_MINE_A",
                metric_name="DEMO_COAL_PRODUCTION",
                metric_value=1350,
                reporting_period="2025-06-30",
                source_reference="sheet Production, row 2",
            )
        ],
    )

    _run(client, doc_a)  # running on A sees B's data too (cross-document scope)
    stored = client.get(f"/api/validation/{doc_a}").json()
    conflicts = [i for i in stored["items"] if i["rule_code"] == "CROSS_DOCUMENT_CONFLICT"]
    assert conflicts, "conflicting values must be detected"
    conflict = conflicts[0]
    assert conflict["status"] == "review_required"

    values = conflict["details"]["values"]
    assert {v["value"] for v in values} == {"1200", "1350"}  # both sides kept
    assert {v["document_id"] for v in values} == {doc_a, doc_b}
    assert all(v["source_reference"] for v in values)
    assert "No winner selected" in conflict["message"]

    # Re-running from B's perspective stores the single group-level conflict
    # under the pair's anchor document (lowest id) — never duplicated per
    # side; reviewers see it globally in the review queue either way.
    _run(client, doc_b)
    stored_anchor = client.get(f"/api/validation/{min(doc_a, doc_b)}").json()
    assert any(
        i["rule_code"] == "CROSS_DOCUMENT_CONFLICT"
        for i in stored_anchor["items"]
    )
    queue = client.get("/api/validation/review-queue").json()
    assert any(
        i["rule_code"] == "CROSS_DOCUMENT_CONFLICT" and i["status"] == "review_required"
        for i in queue["items"]
    )


def test_duplicate_records_flagged_not_deleted(client, migrated_engine):
    document_id = _make_document_with_records(
        migrated_engine,
        "dupes.xlsx",
        [
            dict(
                record_type="coal_production",
                entity_name="DEMO_MINE_A",
                metric_name="DEMO_COAL_PRODUCTION",
                metric_value=1200,
                reporting_period="2025-06-30",
            ),
            dict(
                record_type="coal_production",
                entity_name="DEMO_MINE_A",
                metric_name="DEMO_COAL_PRODUCTION",
                metric_value=1200,
                reporting_period="2025-06-30",
            ),
        ],
    )
    _run(client, document_id)
    stored = client.get(f"/api/validation/{document_id}").json()
    duplicates = [i for i in stored["items"] if i["rule_code"] == "DUPLICATE_DETECTED"]
    assert len(duplicates) == 1
    assert duplicates[0]["status"] == "warning"

    with migrated_engine.connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM extracted_records WHERE document_id = :id"), {"id": document_id}
        ).scalar()
    assert count == 2  # duplicates flagged, never deleted


# --- idempotency / review workflow / errors -------------------------------------------------------


def test_rerunning_validation_replaces_results_without_duplicates(client, migrated_engine):
    document_id = _make_document_with_records(
        migrated_engine,
        "rerun.xlsx",
        [
            dict(
                record_type="coal_production",
                entity_name="DEMO_MINE_A",
                metric_name="DEMO_COAL_PRODUCTION",
                metric_value=1200,
                reporting_period="2025-06-30",
            )
        ],
    )
    first = _run(client, document_id).json()
    second = _run(client, document_id).json()

    assert first["results_created"] == second["results_created"]
    with migrated_engine.connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM validation_results WHERE document_id = :id"), {"id": document_id}
        ).scalar()
    assert count == second["results_created"]  # replaced, not accumulated


def test_review_patch_updates_status_only(client, migrated_engine):
    """A flagged (rule-violating) record can be reviewed: status changes,
    the original value is untouched. A fully valid record produces NO
    results at all (violations only) — hence the negative value here."""
    document_id = _make_document_with_records(
        migrated_engine,
        "review.xlsx",
        [
            dict(
                record_type="coal_production",
                entity_name="DEMO_MINE_A",
                metric_name="DEMO_COAL_PRODUCTION",
                metric_value=-50,  # demo rule: negatives not allowed → flagged
                reporting_period="2025-06-30",
            )
        ],
    )
    _run(client, document_id)
    queue = client.get("/api/validation/review-queue").json()
    assert queue["total"] >= 1
    item = queue["items"][0]

    response = client.patch(
        f"/api/validation/{item['id']}",
        json={"review_status": "resolved", "review_notes": "Checked against source; value correct."},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["review_status"] == "resolved"
    assert body["reviewed_at"] is not None

    # The resolved item left the open queue, and the original value is intact.
    open_queue = client.get("/api/validation/review-queue").json()
    assert all(i["id"] != item["id"] for i in open_queue["items"])
    with migrated_engine.connect() as conn:
        original = conn.execute(
            text("SELECT original_value FROM validation_results WHERE id = :id"), {"id": item["id"]}
        ).scalar()
    assert original == item["original_value"]


def test_review_patch_rejects_invalid_status(client, migrated_engine):
    document_id = _make_document_with_records(
        migrated_engine,
        "review_invalid.xlsx",
        [
            dict(
                record_type="coal_production",
                entity_name="DEMO_MINE_A",
                metric_name="DEMO_COAL_PRODUCTION",
                metric_value=-50,  # flagged so a review item exists to PATCH
                reporting_period="2025-06-30",
            )
        ],
    )
    _run(client, document_id)
    queue = client.get("/api/validation/review-queue").json()
    response = client.patch(
        f"/api/validation/{queue['items'][0]['id']}", json={"review_status": "bananas"}
    )
    assert response.status_code == 422


def test_validation_404_for_unknown_document(client):
    assert client.post("/api/validation/run/999999").status_code == 404
    assert client.get("/api/validation/999999").status_code == 404


def test_validation_returns_503_when_database_unavailable(client, monkeypatch):
    """Unavailable DB ⇒ honest 503, never a fake successful validation."""
    from sqlalchemy.exc import OperationalError

    from app.db import get_db

    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT", {}, Exception("db down"))

        def get(self, *args, **kwargs):
            raise OperationalError("SELECT", {}, Exception("db down"))

    client.app.dependency_overrides[get_db] = lambda: BrokenSession()
    try:
        response = client.post("/api/validation/run/1")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "database_unavailable"
        assert client.get("/api/validation/review-queue").status_code == 503
    finally:
        client.app.dependency_overrides.pop(get_db, None)
