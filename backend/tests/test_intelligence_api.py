"""Step 13 intelligence API integration tests — REQUIRE PostgreSQL (conftest
skip contract: SKIP, never fake-pass, when the database is absent)."""

import pytest

pytestmark = pytest.mark.db


def _make_document(migrated_engine, filename: str, pages_text: list[str]) -> int:
    """Insert a processed document with pages and index them."""
    from datetime import datetime, timezone

    from sqlalchemy.orm import Session

    from app.models import Document, DocumentPage
    from app.services import knowledge_service

    with Session(migrated_engine) as session:
        document = Document(
            filename=filename,
            document_type="pdf",
            storage_reference=f"test/{filename}",
            status="processed",
            processed_at=datetime.now(timezone.utc),
            extraction_status="completed",
        )
        session.add(document)
        session.flush()
        for number, text in enumerate(pages_text, start=1):
            session.add(DocumentPage(
                document_id=document.id,
                page_number=number,
                content_type="page",
                extracted_text=text,
                extraction_status="extracted",
                processing_status="completed",
            ))
        session.commit()
        document_id = document.id
    knowledge_service.index_document(Session(migrated_engine), document_id)
    return document_id


def test_document_intelligence_end_to_end(client, migrated_engine):
    document_id = _make_document(
        migrated_engine,
        "coal_report.pdf",
        [
            "Coal production report for the mine. Coal production output "
            "was reported in tonnes.",
            "Mine planning and safety review. Coal production increased.",
        ],
    )
    response = client.get(f"/api/intelligence/documents/{document_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"] == "document"
    assert payload["summary"]["document_id"] == document_id
    assert payload["summary"]["page_count"] == 2
    assert payload["keywords"], "keywords expected from indexed pages"
    terms = {k["term"] for k in payload["keywords"]}
    assert "coal" in terms and "production" in terms
    phrases = {k["term"] for k in payload["keywords"] if k["kind"] == "phrase"}
    assert "coal production" in phrases
    assert any(t["label"] for t in payload["topics"])
    assert payload["word_cloud"]
    cloud_terms = {w["term"] for w in payload["word_cloud"]}
    assert "coal" in cloud_terms


def test_keyword_sources_carry_provenance(client, migrated_engine):
    document_id = _make_document(
        migrated_engine, "provenance.pdf",
        ["Coal production output tonnes. Coal production increased."],
    )
    payload = client.get(
        f"/api/intelligence/documents/{document_id}/keywords"
    ).json()
    coal = next(k for k in payload["keywords"] if k["term"] == "coal")
    assert coal["sources"]
    source = coal["sources"][0]
    assert source["document_id"] == document_id
    assert source["page_id"] is not None


def test_corpus_analyze_spans_documents(client, migrated_engine):
    _make_document(migrated_engine, "docA.pdf",
                   ["Coal production output tonnes. Coal production."])
    _make_document(migrated_engine, "docB.pdf",
                   ["Mine planning safety. Mine planning review."])
    response = client.post("/api/intelligence/corpus/analyze", json={})
    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"] == "corpus"
    assert len(payload["document_ids"]) == 2
    matches = payload["topic_document_matches"]
    assert any(m["document_id"] == 1 for m in matches)
    assert any(m["document_id"] == 2 for m in matches)


def test_summarize_deterministic_with_ai_unavailable(client, migrated_engine):
    document_id = _make_document(
        migrated_engine, "summary.pdf",
        ["Coal production report. Coal production output tonnes."],
    )
    response = client.post(
        f"/api/intelligence/documents/{document_id}/summarize",
        json={"include_ai_summary": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["record_count"] == 0
    assert "coal" in " ".join(
        t["term"] for t in payload["summary"]["key_terms"]
    )
    # No LLM configured in this environment ⇒ honest unavailable state.
    assert payload["ai_summary"]["state"] == "unavailable"


def test_unknown_document_returns_404(client, migrated_engine):
    response = client.get("/api/intelligence/documents/9999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"


def test_document_without_indexed_content_is_404(client, migrated_engine):
    from datetime import datetime, timezone

    from sqlalchemy.orm import Session

    from app.models import Document

    with Session(migrated_engine) as session:
        document = Document(
            filename="empty.pdf", document_type="pdf",
            storage_reference="test/empty.pdf", status="uploaded",
            uploaded_at=datetime.now(timezone.utc),
        )
        session.add(document)
        session.commit()
        document_id = document.id
    response = client.get(f"/api/intelligence/documents/{document_id}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "no_indexed_content"


def test_intelligence_audit_rows_written(client, migrated_engine):
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.models import AuditLog

    document_id = _make_document(
        migrated_engine, "audit.pdf",
        ["Coal production output tonnes. Coal production."],
    )
    client.get(f"/api/intelligence/documents/{document_id}")
    client.post("/api/intelligence/corpus/analyze", json={})
    client.post(f"/api/intelligence/documents/{document_id}/summarize", json={})
    with Session(migrated_engine) as session:
        actions = set(session.scalars(
            select(AuditLog.action).where(
                AuditLog.action.like("intelligence.%")
            )
        ))
        assert "intelligence.analyze" in actions
        assert "intelligence.summarize" in actions
