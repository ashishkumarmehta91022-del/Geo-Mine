"""Document API integration tests — REQUIRE PostgreSQL (skip contract in conftest.py).

Covers the Step 3 upload/list/detail/download/delete flows end-to-end through
the FastAPI TestClient, with an isolated temp storage directory per run.
"""

import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.conftest import BACKEND_DIR

pytestmark = pytest.mark.db

VALID_PDF = b"%PDF-1.7\n" + b"%" * 256
VALID_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 256
VALID_DOCX = b"PK\x03\x04" + b"[Content_Types].xml...word/document.xml" + b"\x00" * 256
VALID_XLSX = b"PK\x03\x04" + b"[Content_Types].xml...xl/workbook.xml" + b"\x00" * 256
NOT_A_PDF = b"this is definitely not a pdf"


@pytest.fixture()
def client(migrated_engine, monkeypatch, tmp_path):
    """TestClient with isolated temp storage; cleans documents table per test."""
    from app.config import settings
    from app.main import app

    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "documents"))
    import app.api.routes.documents as documents_route
    monkeypatch.setattr(documents_route, "_storage", documents_route.LocalFileStorage(str(tmp_path / "documents")))

    with TestClient(app) as test_client:
        yield test_client

    with migrated_engine.connect() as conn:
        conn.execute(text("TRUNCATE documents, document_pages, extracted_records, validation_results, audit_logs RESTART IDENTITY CASCADE"))
        conn.commit()


def _upload(client, name: str, content: bytes, mime: str | None = None):
    return client.post(
        "/api/documents/upload",
        files={"upload": (name, io.BytesIO(content), mime)},
    )


# --- upload -----------------------------------------------------------------

def test_upload_pdf_succeeds(client, tmp_path):
    response = _upload(client, "geology_report.pdf", VALID_PDF, "application/pdf")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["filename"] == "geology_report.pdf"
    assert body["document_type"] == "pdf"
    assert body["status"] == "uploaded"
    assert body["storage_reference"].endswith(".pdf")
    assert "/" not in body["storage_reference"]  # opaque key, no path exposure

    # Stored file exists under the temp storage root; record is in the DB.
    storage_dir = tmp_path / "documents"
    assert (storage_dir / body["storage_reference"]).is_file()


def test_upload_image_succeeds(client):
    response = _upload(client, "site_photo.png", VALID_PNG, "image/png")
    assert response.status_code == 201, response.text
    assert response.json()["document_type"] == "image"


def test_upload_docx_and_xlsx_succeed(client):
    docx = _upload(client, "notes.docx", VALID_DOCX)
    xlsx = _upload(client, "data.xlsx", VALID_XLSX)
    assert docx.status_code == 201, docx.text
    assert xlsx.status_code == 201, xlsx.text
    assert docx.json()["document_type"] == "docx"
    assert xlsx.json()["document_type"] == "xlsx"


def test_upload_unsupported_extension_rejected(client):
    response = _upload(client, "script.sh", b"#!/bin/sh\necho hi", "application/x-sh")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_file"


def test_upload_invalid_signature_rejected(client, tmp_path):
    response = _upload(client, "fake.pdf", NOT_A_PDF, "application/pdf")
    assert response.status_code == 400
    # Nothing stored for a rejected upload.
    assert list((tmp_path / "documents").iterdir()) == []


def test_upload_oversized_file_rejected(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_upload_size_mb", 1)
    big = b"%PDF-1.7\n" + b"\x00" * (1 * 1024 * 1024 + 100)
    response = _upload(client, "big.pdf", big, "application/pdf")
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_upload_path_traversal_filename_is_sanitized(client):
    response = _upload(client, "../../etc/passwd_report.pdf", VALID_PDF, "application/pdf")
    assert response.status_code == 201, response.text
    assert response.json()["filename"] == "passwd_report.pdf"


def test_filename_collision_generates_distinct_keys(client, tmp_path):
    first = _upload(client, "same_name.pdf", VALID_PDF, "application/pdf").json()
    second = _upload(client, "same_name.pdf", VALID_PDF, "application/pdf").json()
    assert first["storage_reference"] != second["storage_reference"]
    files = sorted(p.name for p in (tmp_path / "documents").iterdir())
    assert files == sorted([first["storage_reference"], second["storage_reference"]])


def test_upload_registers_database_record(client, migrated_engine):
    body = _upload(client, "recorded.pdf", VALID_PDF, "application/pdf").json()
    with migrated_engine.connect() as conn:
        row = conn.execute(
            text("SELECT filename, document_type, source, status FROM documents WHERE id = :id"),
            {"id": body["id"]},
        ).one()
    assert row.filename == "recorded.pdf"
    assert row.document_type == "pdf"
    assert row.source == "upload"
    assert row.status == "uploaded"


# --- database-failure cleanup -------------------------------------------------

def test_database_failure_cleans_up_stored_file(client, monkeypatch, tmp_path):
    """If DB registration fails after the file is stored, the orphan file is removed."""
    import app.api.routes.documents as documents_route
    from app.exceptions import AppError
    from sqlalchemy.orm import Session

    class BrokenSession(Session):
        def commit(self):
            raise AppError(status_code=500, code="boom", message="db down")

    import app.services.document_service as service_module
    original = service_module.Session

    def broken_session_factory(*args, **kwargs):
        session = Session()
        session.commit = lambda: (_ for _ in ()).throw(AppError(status_code=500, code="boom", message="db down"))
        return session

    # Patch the route-level dependency to hand out a session whose commit fails.
    from app.db import get_db
    app = client.app
    app.dependency_overrides[get_db] = lambda: broken_session_factory()

    try:
        response = _upload(client, "orphan_check.pdf", VALID_PDF, "application/pdf")
        assert response.status_code == 500
        # The storage dir must not keep an orphaned file.
        assert list((tmp_path / "documents").iterdir()) == []
    finally:
        app.dependency_overrides.pop(get_db, None)


# --- list / detail / download / delete -----------------------------------------

def test_document_list_pagination(client):
    for i in range(7):
        assert _upload(client, f"doc_{i}.pdf", VALID_PDF, "application/pdf").status_code == 201

    page1 = client.get("/api/documents?page=1&page_size=3").json()
    page3 = client.get("/api/documents?page=3&page_size=3").json()
    assert page1["total"] == 7 and len(page1["items"]) == 3
    assert page3["total"] == 7 and len(page3["items"]) == 1
    ids = {d["id"] for d in page1["items"]} | {d["id"] for d in page3["items"]}
    assert len(ids) == 7
    # Newest first.
    assert page1["items"][0]["id"] > page1["items"][-1]["id"]


def test_document_detail_returns_metadata(client):
    body = _upload(client, "detail.pdf", VALID_PDF, "application/pdf").json()
    detail = client.get(f"/api/documents/{body['id']}")
    assert detail.status_code == 200
    assert detail.json()["filename"] == "detail.pdf"
    assert detail.json()["id"] == body["id"]


def test_download_returns_original_content_and_filename(client):
    content = VALID_PDF + b"EXTRA-DOWNLOAD-CHECK"
    body = _upload(client, "download_me.pdf", content, "application/pdf").json()
    response = client.get(f"/api/documents/{body['id']}/download")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert "attachment" in response.headers.get("content-disposition", "")
    assert "download_me.pdf" in response.headers.get("content-disposition", "")
    assert response.content == content


def test_missing_document_returns_404(client):
    assert client.get("/api/documents/999999").status_code == 404
    assert client.get("/api/documents/999999/download").status_code == 404
    assert client.delete("/api/documents/999999").status_code == 404


def test_delete_removes_record_and_stored_file(client, migrated_engine, tmp_path):
    body = _upload(client, "delete_me.pdf", VALID_PDF, "application/pdf").json()
    key = body["storage_reference"]
    assert (tmp_path / "documents" / key).is_file()

    response = client.delete(f"/api/documents/{body['id']}")
    assert response.status_code == 204

    with migrated_engine.connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM documents WHERE id = :id"), {"id": body["id"]}
        ).scalar()
    assert count == 0
    assert not (tmp_path / "documents" / key).exists()
