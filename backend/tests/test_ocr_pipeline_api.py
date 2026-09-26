"""OCR pipeline integration tests — REQUIRE PostgreSQL (conftest.py skip contract).

Covers scanned PDFs, mixed PDFs (independent per-page methods), image OCR,
traceability, idempotent re-processing and review flagging through the API.
"""

import io

import pytest
from sqlalchemy import text

from tests.processing_fixtures import (
    corrupted_pdf_bytes,
    pdf_bytes,
    pdf_bytes_with_image_pages,
    png_bytes,
    rendered_text_image_bytes,
)

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


def _content(client, document_id: int) -> dict:
    response = client.get(f"/api/documents/{document_id}/content")
    assert response.status_code == 200, response.text
    return response.json()


# --- scanned / mixed PDFs ---------------------------------------------------------


def test_image_only_pdf_pages_are_ocr_processed(client):
    body = _upload(client, "scan.pdf", pdf_bytes_with_image_pages([None, None]), "application/pdf")
    payload = _process(client, body["id"]).json()

    assert payload["status"] == "processed"
    content = _content(client, body["id"])
    assert all(section["extraction_status"] == "ocr_extracted" for section in content["sections"])
    # Page-number provenance preserved for every OCR page.
    assert [s["number"] for s in content["sections"]] == [1, 2]
    for section in content["sections"]:
        assert section["ocr"]["engine"] == "rapidocr-onnxruntime"
        assert "12345" in section["text"].replace(" ", "")  # digits verbatim


def test_mixed_pdf_processes_each_page_independently(client):
    body = _upload(
        client,
        "mixed.pdf",
        pdf_bytes_with_image_pages(["Native page one text", None, "Native page three text", None]),
        "application/pdf",
    )
    payload = _process(client, body["id"]).json()
    assert payload["status"] == "processed"

    content = _content(client, body["id"])
    statuses = [s["extraction_status"] for s in content["sections"]]
    # Exactly the scanned pages are OCR; native pages keep native extraction.
    assert statuses == ["extracted", "ocr_extracted", "extracted", "ocr_extracted"]
    assert content["extraction_status"] == "mixed"

    # Native pages must NOT carry OCR metadata; OCR pages must.
    assert content["sections"][0].get("ocr") is None
    assert content["sections"][1]["ocr"]["engine"] == "rapidocr-onnxruntime"
    assert content["sections"][2].get("ocr") is None
    assert content["sections"][3]["ocr"]["engine"] == "rapidocr-onnxruntime"

    # Source references identify the PDF page for both paths.
    assert [s["reference"] for s in content["sections"]] == [
        "page 1", "page 2", "page 3", "page 4",
    ]


def test_native_pdf_unchanged_by_ocr_layer(client):
    body = _upload(client, "native.pdf", pdf_bytes(["Just native text"]), "application/pdf")
    payload = _process(client, body["id"]).json()
    assert payload["status"] == "processed"
    assert payload["statistics"]["extracted"] == 1
    assert payload["statistics"]["ocr_extracted"] == 0

    content = _content(client, body["id"])
    assert content["sections"][0]["extraction_status"] == "extracted"
    assert content["sections"][0].get("ocr") is None  # no unnecessary OCR


def test_image_document_ocr_end_to_end(client):
    body = _upload(client, "scan.png", rendered_text_image_bytes("DEMO 67890"), "image/png")
    payload = _process(client, body["id"]).json()

    assert payload["status"] == "processed"
    assert payload["statistics"]["ocr_extracted"] == 1

    content = _content(client, body["id"])
    section = content["sections"][0]
    assert section["type"] == "image"
    assert section["extraction_status"] == "ocr_extracted"
    assert section["reference"] == "image"
    assert "67890" in section["text"].replace(" ", "")
    assert section["ocr"]["bounding_boxes"]
    assert section["ocr"]["confidence"] is not None


def test_scanned_page_failure_does_not_corrupt_native_pages(client, monkeypatch):
    """One broken OCR page must not fail the document's healthy pages."""
    body = _upload(
        client,
        "partial.pdf",
        pdf_bytes_with_image_pages(["Healthy native page", None]),
        "application/pdf",
    )

    # Force the OCR path to fail (engine explosion) without touching native extraction.
    from app.processing.ocr.service import set_ocr_engine

    class ExplodingEngine:
        name = "exploding"
        version = "0"

        def extract(self, image_bytes):
            raise RuntimeError("OCR engine exploded")

    set_ocr_engine(ExplodingEngine())
    try:
        payload = _process(client, body["id"]).json()
    finally:
        set_ocr_engine(None)

    assert payload["status"] == "processed"  # document completes...
    content = _content(client, body["id"])
    statuses = [s["extraction_status"] for s in content["sections"]]
    assert statuses == ["extracted", "failed"]  # ...and the failed page is isolated
    assert "exploded" in (content["sections"][1]["ocr"] or {}).get("error", "")


# --- traceability / idempotency / review ----------------------------------------------


def test_ocr_traceability_chain_document_page_result(client, migrated_engine):
    body = _upload(client, "trace.pdf", pdf_bytes_with_image_pages([None]), "application/pdf")
    _process(client, body["id"])

    with migrated_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT document_id, page_number, section_reference, extraction_status, "
                "extractor_name, extractor_version, extracted_at, structured_metadata "
                "FROM document_pages WHERE document_id = :id"
            ),
            {"id": body["id"]},
        ).one()

    assert row.document_id == body["id"]
    assert row.page_number == 1
    assert row.section_reference == "page 1"
    assert row.extraction_status == "ocr_extracted"
    assert row.extractor_name == "pymupdf+ocr"
    assert row.extractor_version
    assert row.extracted_at is not None
    ocr_meta = row.structured_metadata["ocr"]
    assert ocr_meta["engine"] == "rapidocr-onnxruntime"
    assert ocr_meta["engine_version"]
    assert isinstance(ocr_meta["bounding_boxes"], list)


def test_reprocessing_ocr_document_is_idempotent(client, migrated_engine):
    body = _upload(client, "twice_scan.pdf", pdf_bytes_with_image_pages([None, None]), "application/pdf")
    _process(client, body["id"])
    _process(client, body["id"])

    with migrated_engine.connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM document_pages WHERE document_id = :id"), {"id": body["id"]}
        ).scalar()
    assert count == 2  # replaced, never duplicated


def test_low_confidence_ocr_flags_review(client, monkeypatch):
    """A low-confidence OCR result is stored verbatim and flagged review_required."""
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
        assert payload["status"] == "processed"

        content = _content(client, body["id"])
        section = content["sections"][0]
        assert section["text"] == "1O5"  # verbatim — never silently corrected to 105
        assert section["ocr"]["review_required"] is True
        assert section["ocr"]["low_confidence_count"] == 1
    finally:
        set_ocr_engine(None)


def test_corrupted_pdf_still_fails_cleanly(client):
    body = _upload(client, "broken.pdf", corrupted_pdf_bytes(), "application/pdf")
    response = _process(client, body["id"])
    assert response.status_code == 422
    status = client.get(f"/api/documents/{body['id']}/processing-status").json()
    assert status["status"] == "failed"
    assert status["error_message"]
