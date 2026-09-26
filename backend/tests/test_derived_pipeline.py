"""Derived-data pipeline tests — REQUIRE PostgreSQL (conftest.py skip contract).

Verifies: process → structured records → automatic validation, idempotent
re-processing, status honesty and failure isolation.
"""

import io

import pytest
from sqlalchemy import text

from tests.processing_fixtures import pdf_bytes, xlsx_bytes

pytestmark = pytest.mark.db


def _upload(client, name: str, content: bytes, mime: str | None = None) -> dict:
    response = client.post(
        "/api/documents/upload",
        files={"upload": (name, io.BytesIO(content), mime)},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _process(client, document_id: int):
    return client.post(f"/api/documents/{document_id}/process")


def _status(client, document_id: int) -> dict:
    return client.get(f"/api/documents/{document_id}/processing-status").json()


# --- the core workflow --------------------------------------------------------------


def test_process_creates_records_and_runs_validation_automatically(client, migrated_engine):
    sheets = {
        "Production": [
            ["Mine", "Value", "Unit", "Period"],
            ["DEMO_MINE_A", "1,200", "tonnes", "2025-06-30"],
        ],
    }
    body = _upload(client, "auto.xlsx", xlsx_bytes(sheets))
    result = _process(client, body["id"])
    assert result.status_code == 202, result.text
    payload = result.json()

    # Combined state exposed in one response, from real DB values.
    assert payload["status"] == "processed"
    assert payload["records_extracted"] >= 1
    assert payload["validation"]["total_checks"] >= 0
    assert payload["validation_status"] in {"pass", "warning", "error", "review_required", None}

    # Structured records actually persisted with Step 7 fields.
    with migrated_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT value_raw, normalized_value, extraction_method, source_reference "
                "FROM extracted_records WHERE document_id = :id"
            ),
            {"id": body["id"]},
        ).all()
    assert rows, "structured records must exist after processing"
    assert rows[0][0] == "1,200"  # value_raw verbatim
    assert rows[0][1] == "1200"  # normalized
    assert rows[0][2] == "spreadsheet"
    assert "Production" in rows[0][3] and "row" in rows[0][3]

    # Validation results exist and are linked to the document.
    with migrated_engine.connect() as conn:
        validation_count = conn.execute(
            text("SELECT count(*) FROM validation_results WHERE document_id = :id"),
            {"id": body["id"]},
        ).scalar()
    assert validation_count >= 1  # auto-validation ran (required-field/date rules fired)


def test_records_survive_with_provenance_and_validation_rollup(client, migrated_engine):
    """Record values flagged by rules keep their values; status reflects the rules."""
    sheets = {
        "Production": [
            ["Mine", "Value", "Unit", "Period"],
            ["DEMO_MINE_A", "-50", "tonnes", "2025-06-30"],  # demo rule: negatives invalid
        ],
    }
    body = _upload(client, "negative.xlsx", xlsx_bytes(sheets))
    payload = _process(client, body["id"]).json()

    assert payload["validation_status"] == "error"  # visible, not hidden
    with migrated_engine.connect() as conn:
        value_raw, validation_status = conn.execute(
            text("SELECT value_raw, validation_status FROM extracted_records WHERE document_id = :id"),
            {"id": body["id"]},
        ).one()
    assert value_raw == "-50"  # original preserved
    assert validation_status == "failed"  # flagged by the numeric rule


def test_ocr_low_confidence_keeps_document_review_required(client, migrated_engine, monkeypatch):
    """OCR review flag must surface on the document — not be collapsed into success."""
    from app.processing.ocr.base import OcrBoundingBox, OcrResult
    from app.processing.ocr.service import set_ocr_engine

    low_box = OcrBoundingBox(text="1O5", x1=0, y1=0, x2=10, y2=10, confidence=0.42)
    set_ocr_engine(
        type(
            "LowConfEngine",
            (),
            {
                "name": "fake-low",
                "version": "0",
                "extract": lambda self, b: OcrResult(
                    text="1O5",
                    confidence=0.42,
                    bounding_boxes=(low_box,),
                    review_required=True,
                    low_confidence_boxes=(low_box,),
                    engine_metadata={"engine": "fake-low", "engine_version": "0"},
                ),
            },
        )()
    )
    try:
        body = _upload(client, "lowconf.png", png_bytes(60, 40), "image/png")
        payload = _process(client, body["id"]).json()
    finally:
        set_ocr_engine(None)

    assert payload["status"] == "processed"  # processing itself succeeded
    assert payload["validation_status"] == "review_required"  # ...but review stays visible
    with migrated_engine.connect() as conn:
        value_raw = conn.execute(
            text("SELECT value_raw FROM extracted_records WHERE document_id = :id"), {"id": body["id"]}
        ).scalar()
    assert value_raw == "1O5"  # verbatim OCR text in the structured layer too


def png_bytes(w, h):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(buffer, format="PNG")
    return buffer.getvalue()


# --- idempotency ------------------------------------------------------------------------


def test_reprocessing_replaces_records_without_duplicates(client, migrated_engine):
    sheets = {
        "Production": [
            ["Mine", "Value", "Unit", "Period"],
            ["DEMO_MINE_A", "100", "tonnes", "2025-03-31"],
            ["DEMO_MINE_B", "200", "tonnes", "2025-03-31"],
        ],
    }
    body = _upload(client, "idempotent.xlsx", xlsx_bytes(sheets))

    _process(client, body["id"])
    _process(client, body["id"])
    third = _process(client, body["id"]).json()

    with migrated_engine.connect() as conn:
        records = conn.execute(
            text("SELECT count(*) FROM extracted_records WHERE document_id = :id"), {"id": body["id"]}
        ).scalar()
        validations = conn.execute(
            text("SELECT count(*) FROM validation_results WHERE document_id = :id"), {"id": body["id"]}
        ).scalar()
    assert records == 2  # 2 after run 1, still 2 after run 3
    assert validations == third["validation"]["total_checks"]


def test_reprocess_after_content_change_replaces_derived_data(client, migrated_engine):
    """Simulate a 'fixed' file: derived data reflects the latest content only."""
    sheets_v1 = {"Production": [["Mine", "Value"], ["DEMO_MINE_A", "100"]]}
    sheets_v2 = {"Production": [["Mine", "Value"], ["DEMO_MINE_A", "100"], ["DEMO_MINE_B", "200"]]}

    body = _upload(client, "versioned.xlsx", xlsx_bytes(sheets_v1))
    _process(client, body["id"])
    _process(client, body["id"])

    # Overwrite the stored file with v2 content and reprocess.
    import app.api.routes.documents as documents_route
    from pathlib import Path

    stored_path = Path(body["storage_reference"])
    # Write v2 through the storage abstraction of the route under test.
    documents_route._storage.save(stored_path, iter([xlsx_bytes(sheets_v2)]))
    _process(client, body["id"])

    with migrated_engine.connect() as conn:
        entities = conn.execute(
            text("SELECT entity_name FROM extracted_records WHERE document_id = :id"),
            {"id": body["id"]},
        ).scalars().all()
    assert sorted(entities) == ["DEMO_MINE_A", "DEMO_MINE_B"]  # v2 only, no stale v1 rows


# --- failure isolation ----------------------------------------------------------------------


def test_extraction_failure_leaves_no_stale_validation_success(client, migrated_engine):
    """A failed reprocess must not leave the old 'validated' shine on the document."""
    from app.constants import DocumentStatus

    body = _upload(client, "later_broken.pdf", pdf_bytes(["healthy text"]), "application/pdf")
    _process(client, body["id"])  # first run OK
    assert _status(client, body["id"])["status"] == "processed"

    # Corrupt the stored file, then reprocess — must fail honestly.
    import app.api.routes.documents as documents_route
    from pathlib import Path

    documents_route._storage.save(Path(body["storage_reference"]), iter([b"corrupted garbage"]))

    response = _process(client, body["id"])
    assert response.status_code == 422
    assert _status(client, body["id"])["status"] == "failed"
    with migrated_engine.connect() as conn:
        error = conn.execute(
            text("SELECT error_message FROM documents WHERE id = :id"), {"id": body["id"]}
        ).scalar()
    assert error  # real error preserved


def test_records_endpoint_filters_by_exact_dimensions(client, migrated_engine):
    sheets = {
        "Production": [
            ["Mine", "Value", "Unit", "Period"],
            ["DEMO_MINE_A", "100", "tonnes", "2025-03-31"],
            ["DEMO_MINE_B", "200", "tonnes", "2025-06-30"],
        ],
    }
    body = _upload(client, "explorer.xlsx", xlsx_bytes(sheets))
    _process(client, body["id"])

    all_records = client.get("/api/records").json()
    assert all_records["total"] >= 2

    filtered = client.get("/api/records", params={"entity": "DEMO_MINE_A"}).json()
    assert filtered["total"] >= 1
    assert all(item["entity_name"] == "DEMO_MINE_A" for item in filtered["items"])

    by_method = client.get("/api/records", params={"extraction_method": "spreadsheet"}).json()
    assert by_method["total"] >= 1
    assert all(i["extraction_method"] == "spreadsheet" for i in by_method["items"])
