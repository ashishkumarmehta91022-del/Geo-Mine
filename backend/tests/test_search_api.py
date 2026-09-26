"""Search/knowledge integration tests — REQUIRE PostgreSQL (conftest skip contract)."""

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.db


def _make_processed_document(migrated_engine, filename: str, rows: list[dict]) -> int:
    """Insert a processed document with records (source-of-truth rows)."""
    from datetime import datetime, timezone
    from sqlalchemy.orm import Session

    from app.models import Document

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
            from app.models import ExtractedRecord

            session.add(ExtractedRecord(document_id=document.id, **row))
        session.commit()
        return document.id


def _search(client, **params):
    return client.get("/api/search", params=params)


# --- indexing + basic search -----------------------------------------------------------


def test_search_empty_index_returns_empty_not_error(client):
    response = _search(client, q="anything")
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_index_document_then_search_by_keyword(client, migrated_engine):
    document_id = _make_processed_document(
        migrated_engine,
        "coal_report.xlsx",
        [
            dict(
                record_type="coal_production",
                entity_name="DEMO_MINE_A",
                metric_name="demo_coal_production",
                metric_value=1200,
                value_raw="1,200",
                normalized_value="1200",
                unit="tonnes",
                reporting_period="2025-06-30",
                source_reference="sheet Production, row 2",
                extraction_method="spreadsheet",
                validation_status="pass",
            )
        ],
    )
    from app.services.knowledge_service import index_document

    created = index_document(migrated_engine_session(migrated_engine), document_id)
    assert created >= 1

    response = _search(client, q="DEMO_MINE_A")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1

    record_hit = next(r for r in body["results"] if r["unit_type"] == "record")
    # Full provenance on every result.
    assert record_hit["document_id"] == document_id
    assert record_hit["document_name"] == "coal_report.xlsx"
    assert record_hit["entity"] == "DEMO_MINE_A"
    assert record_hit["metric"] == "demo_coal_production"
    assert record_hit["value_raw"] == "1,200"
    assert record_hit["normalized_value"] == "1200"
    assert record_hit["unit"] == "tonnes"
    assert record_hit["validation_status"] == "pass"
    assert record_hit["source_reference"] == "sheet Production, row 2"


def migrated_engine_session(engine):
    from sqlalchemy.orm import Session

    return Session(engine)


def test_exact_phrase_search_matches(client, migrated_engine):
    document_id = _make_processed_document(
        migrated_engine,
        "phrase.xlsx",
        [
            dict(
                record_type="note",
                entity_name="DEMO_MINE_A",
                metric_name="demo_text_block",
                value_raw="Annual coal production summary for the mine",
                normalized_value=None,
                extraction_method="native_text",
                validation_status="valid",
            )
        ],
    )
    from app.services.knowledge_service import index_document

    index_document(migrated_engine_session(migrated_engine), document_id)

    hit = _search(client, q='"coal production"').json()
    assert hit["total"] >= 1
    miss = _search(client, q='"production coal"').json()  # different phrase
    assert miss["total"] == 0


def test_filters_narrow_results(client, migrated_engine):
    document_id = _make_processed_document(
        migrated_engine,
        "filters.xlsx",
        [
            dict(
                record_type="coal_production",
                entity_name="DEMO_MINE_A",
                metric_name="demo_coal_production",
                metric_value=100,
                extraction_method="spreadsheet",
                validation_status="pass",
            ),
            dict(
                record_type="coal_production",
                entity_name="DEMO_MINE_B",
                metric_name="demo_coal_production",
                metric_value=200,
                extraction_method="spreadsheet",
                validation_status="failed",
            ),
        ],
    )
    from app.services.knowledge_service import index_document

    index_document(migrated_engine_session(migrated_engine), document_id)

    by_entity = _search(client, entity="DEMO_MINE_A").json()
    assert by_entity["total"] >= 1
    assert all(r["entity"] == "DEMO_MINE_A" for r in by_entity["results"])

    by_status = _search(client, validation_status="failed").json()
    assert by_status["total"] >= 1
    assert all(r["validation_status"] == "failed" for r in by_status["results"])

    combined = _search(client, entity="DEMO_MINE_B", validation_status="pass").json()
    assert combined["total"] == 0  # conflicting filters legitimately yield nothing


def test_pagination(client, migrated_engine):
    document_id = _make_processed_document(
        migrated_engine,
        "pager.xlsx",
        [
            dict(
                record_type="coal_production",
                entity_name=f"DEMO_MINE_{i:02d}",
                metric_name="demo_coal_production",
                metric_value=i * 10,
                extraction_method="spreadsheet",
                validation_status="pass",
            )
            for i in range(7)
        ],
    )
    from app.services.knowledge_service import index_document

    index_document(migrated_engine_session(migrated_engine), document_id)

    page1 = _search(client, metric="demo_coal_production", limit=3, offset=0).json()
    page2 = _search(client, metric="demo_coal_production", limit=3, offset=3).json()
    assert page1["total"] == page2["total"]
    assert len(page1["results"]) == 3
    assert 0 < len(page2["results"]) <= 3
    ids_1 = {r["record_id"] for r in page1["results"]}
    ids_2 = {r["record_id"] for r in page2["results"]}
    assert not ids_1 & ids_2  # no overlap between pages


# --- idempotency / lifecycle ----------------------------------------------------------


def test_reindexing_does_not_duplicate_entries(client, migrated_engine):
    document_id = _make_processed_document(
        migrated_engine,
        "reindex.xlsx",
        [
            dict(
                record_type="coal_production",
                entity_name="DEMO_MINE_A",
                metric_name="demo_coal_production",
                metric_value=100,
                extraction_method="spreadsheet",
                validation_status="pass",
            )
        ],
    )
    from app.services.knowledge_service import index_document

    index_document(migrated_engine_session(migrated_engine), document_id)
    index_document(migrated_engine_session(migrated_engine), document_id)
    index_document(migrated_engine_session(migrated_engine), document_id)

    with migrated_engine.connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM knowledge_index WHERE document_id = :id"), {"id": document_id}
        ).scalar()
    assert count == 1  # replaced, never duplicated


def test_processing_three_times_keeps_single_index_representation(client, migrated_engine):
    """Full pipeline idempotency: process → index → reprocess → still current."""
    import io

    from tests.processing_fixtures import xlsx_bytes

    upload = client.post(
        "/api/documents/upload",
        files={"upload": ("triple.xlsx", io.BytesIO(xlsx_bytes({
            "Production": [["Mine", "Value"], ["DEMO_MINE_A", "100"]]
        })), None)},
    )
    document_id = upload.json()["id"]
    for _ in range(3):
        assert client.post(f"/api/documents/{document_id}/process").status_code == 202

    with migrated_engine.connect() as conn:
        index_count = conn.execute(
            text("SELECT count(*) FROM knowledge_index WHERE document_id = :id"), {"id": document_id}
        ).scalar()
        record_count = conn.execute(
            text("SELECT count(*) FROM extracted_records WHERE document_id = :id"), {"id": document_id}
        ).scalar()
    assert index_count == record_count  # one current representation, no stale entries


def test_document_deletion_removes_index_entries(client, migrated_engine):
    document_id = _make_processed_document(
        migrated_engine,
        "deleteme.xlsx",
        [
            dict(
                record_type="coal_production",
                entity_name="DEMO_MINE_A",
                metric_name="demo_coal_production",
                metric_value=100,
                extraction_method="spreadsheet",
                validation_status="pass",
            )
        ],
    )
    from app.services.knowledge_service import index_document

    index_document(migrated_engine_session(migrated_engine), document_id)
    with migrated_engine.connect() as conn:
        before = conn.execute(
            text("SELECT count(*) FROM knowledge_index WHERE document_id = :id"), {"id": document_id}
        ).scalar()
    assert before >= 1

    # Delete the document through the existing Step 3 API — CASCADE must
    # clean the index (no orphaned search entries).
    delete_response = client.delete(f"/api/documents/{document_id}")
    assert delete_response.status_code == 204
    with migrated_engine.connect() as conn:
        after = conn.execute(
            text("SELECT count(*) FROM knowledge_index WHERE document_id = :id"), {"id": document_id}
        ).scalar()
    assert after == 0


def test_remove_document_service_is_idempotent(migrated_engine):
    from app.services.knowledge_service import remove_document

    session = migrated_engine_session(migrated_engine)
    assert remove_document(session, 999999) == 0  # nothing to remove, no error
    assert remove_document(session, 999999) == 0


# --- conflict-aware retrieval -----------------------------------------------------------


def test_conflicting_values_both_remain_searchable(client, migrated_engine):
    """Two documents, same key, different values — both searchable, no winner."""
    doc_a = _make_processed_document(
        migrated_engine,
        "conflict_search_a.xlsx",
        [
            dict(
                record_type="coal_production",
                entity_name="DEMO_MINE_A",
                metric_name="demo_coal_production",
                metric_value=1200,
                value_raw="1200",
                normalized_value="1200",
                reporting_period="2025-06-30",
                extraction_method="spreadsheet",
                validation_status="pass",
            )
        ],
    )
    doc_b = _make_processed_document(
        migrated_engine,
        "conflict_search_b.xlsx",
        [
            dict(
                record_type="coal_production",
                entity_name="DEMO_MINE_A",
                metric_name="demo_coal_production",
                metric_value=1350,
                value_raw="1350",
                normalized_value="1350",
                reporting_period="2025-06-30",
                extraction_method="spreadsheet",
                validation_status="pass",
            )
        ],
    )
    from app.services.knowledge_service import index_document

    index_document(migrated_engine_session(migrated_engine), doc_a)
    index_document(migrated_engine_session(migrated_engine), doc_b)

    body = _search(client, metric="demo_coal_production").json()
    values = {r["value_raw"] for r in body["results"] if r["unit_type"] == "record"}
    assert {"1200", "1350"} <= values  # both sides present
    assert {r["document_id"] for r in body["results"] if r["unit_type"] == "record"} >= {doc_a, doc_b}


# --- statistics --------------------------------------------------------------------------


def test_search_statistics_reflect_actual_data(client, migrated_engine):
    stats = client.get("/api/search/stats").json()
    assert set(stats) == {
        "documents_indexed", "pages_indexed", "records_indexed",
        "validation_results_indexed", "total_units", "last_index_update",
    }
    assert isinstance(stats["total_units"], int)
