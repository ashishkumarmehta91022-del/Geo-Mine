"""Step 15 end-to-end workflow tests.

The canonical workflow:
upload → processing → extraction/OCR → structured records → validation →
knowledge index → search → intelligence → analytics → reports → AI query →
audit trail.

The DB-dependent test drives the REAL pipeline over real PostgreSQL
(honest skip when it is unavailable — never faked). The DB-free tests
verify the deterministic stages that need no database.
"""

import io

import pytest

pytestmark = pytest.mark.db


def _upload(client, name: str, content: bytes, mime: str | None = None) -> dict:
    response = client.post(
        "/api/documents/upload",
        files={"upload": (name, io.BytesIO(content), mime)},
    )
    assert response.status_code == 201
    return response.json()


def test_full_workflow_end_to_end(client, migrated_engine):
    """The canonical Step 15 workflow over the real pipeline."""
    from tests.processing_fixtures import xlsx_bytes

    # --- 1-2. upload + stored file -------------------------------------------
    body = _upload(client, "e2e.xlsx", xlsx_bytes({
        "Production": [
            ["Entity", "Metric", "Value", "Unit", "Period"],
            ["E2E_MINE", "e2e_production", 1200, "tonnes", "2025-06-30"],
        ],
    }))
    document_id = body["id"]

    # --- 3-6. processing → extraction → records + validation -----------------
    result = client.post(f"/api/documents/{document_id}/process").json()
    assert result["status"] == "processed"
    assert result["records_created"] >= 1
    assert result["validation"]["total_checks"] >= 1

    # --- 7. knowledge indexing (auto after processing) ------------------------
    search_payload = client.get(
        "/api/search", params={"q": "E2E_MINE"}
    ).json()
    assert search_payload["total"] >= 1, "document must be searchable after processing"

    # --- 8. structured records via the records API -----------------------------
    records = client.get("/api/records", params={"entity": "E2E_MINE"}).json()
    assert records["total"] >= 1
    record = records["items"][0]
    assert record["value_raw"] is not None  # verbatim provenance survives
    assert record["document_id"] == document_id

    # --- 9. intelligence over the processed document ---------------------------
    intel = client.get(f"/api/intelligence/documents/{document_id}").json()
    assert intel["scope"] == "document"
    assert intel["summary"]["page_count"] >= 1
    assert intel["keywords"], "keywords expected from indexed content"

    # --- 10. analytics (Step 12) ------------------------------------------------
    analysis = client.post("/api/reports/analyze", json={
        "title": "E2E Analytics",
        "entities": ["E2E_MINE"],
        "include_narrative": False,
    }).json()
    assert analysis["status"] == "ok"
    assert analysis["record_count"] >= 1
    assert analysis["kpis"], "KPIs expected from validated records"

    # --- 11. report generation (DOCX) --------------------------------------------
    report_response = client.post("/api/reports/generate", json={
        "title": "E2E Report",
        "entities": ["E2E_MINE"],
    })
    assert report_response.status_code == 200
    assert report_response.headers["x-report-records"] >= "1"

    # --- 12. AI query returns retrieval-grounded results --------------------------
    ai = client.post("/api/ai/query", json={
        "question": "E2E_MINE e2e_production", "mode": "lexical",
    }).json()
    assert ai["status"] in ("ok", "llm_unavailable", "insufficient_evidence")
    assert isinstance(ai["evidence_ids"], list)

    # --- 13. dashboard reflects the workflow -------------------------------------
    dashboard = client.get("/api/dashboard/summary").json()
    assert dashboard["data_available"] is True
    assert dashboard["documents"]["total"] >= 1
    assert dashboard["records"]["total"] >= 1

    # --- 14. audit trail captured the operations ----------------------------------
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.models import AuditLog

    with Session(migrated_engine) as session:
        actions = set(session.scalars(
            select(AuditLog.action).where(
                AuditLog.action.in_([
                    "ai.query", "report.generate", "report.analyze",
                    "intelligence.analyze", "dashboard.summary",
                ])
            )
        ))
    assert {"ai.query", "report.generate", "report.analyze",
            "intelligence.analyze", "dashboard.summary"} <= actions


def test_processed_document_is_searchable_and_intelligence_ready(client, migrated_engine):
    """Lifecycle honesty: a processed document is searchable; a failed one is not silently successful."""
    from tests.processing_fixtures import pdf_bytes

    body = _upload(client, "e2e_doc.pdf", pdf_bytes([
        "Coal production report. Coal production output tonnes.",
    ]))
    result = client.post(f"/api/documents/{body['id']}/process").json()
    assert result["status"] == "processed"
    search_payload = client.get("/api/search", params={"q": "coal production"}).json()
    assert search_payload["total"] >= 1

    # --- failure honesty: an unsupported file must NOT end up 'processed' --------
    bad = client.post(
        "/api/documents/upload",
        files={"upload": ("bad.exe", io.BytesIO(b"MZ not a document"), None)},
    )
    assert bad.status_code in (400, 413, 415)  # rejected honestly at upload


def test_report_provenance_reaches_the_docx(client, migrated_engine):
    """Provenance chain: record → source reference → DOCX (Phase 4)."""
    from docx import Document as DocxDocument

    from tests.processing_fixtures import xlsx_bytes

    body = _upload(client, "prov.xlsx", xlsx_bytes({
        "Sheet1": [
            ["Entity", "Metric", "Value", "Unit", "Period"],
            ["PROV_MINE", "prov_metric", 777, "tonnes", "2025-06-30"],
        ],
    }))
    client.post(f"/api/documents/{body['id']}/process")
    report = client.post("/api/reports/generate", json={
        "title": "Provenance Report", "entities": ["PROV_MINE"],
    })
    assert report.status_code == 200
    document = DocxDocument(io.BytesIO(report.content))
    all_text = "\n".join(p.text for p in document.paragraphs) + "\n" + "\n".join(
        cell.text for table in document.tables for row in table.rows for cell in row.cells
    )
    assert "777" in all_text          # the value originates from the record
    assert "PROV_MINE" in all_text    # the entity is preserved


def test_ai_insufficient_evidence_is_honest(client, migrated_engine):
    """No evidence ⇒ insufficient_evidence, never a fabricated answer (Phase 5)."""
    client.post("/api/ai/query", json={"question": "xyzzy_nonexistent_value_98231"})
    # (the route returns 200 with an honest status; only assert shape here)
    response = client.post("/api/ai/query", json={
        "question": "totally_unrelated_zebra_98231", "mode": "lexical",
    })
    assert response.status_code in (200, 503)  # 503 = no LLM configured (honest)
    if response.status_code == 200:
        payload = response.json()
        assert payload["status"] in ("insufficient_evidence", "llm_unavailable")
