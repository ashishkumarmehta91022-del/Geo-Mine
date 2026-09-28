"""Step 14 dashboard tests — DB-free.

Covers: response schema via pure builders, honest status mapping, empty-state
behavior (no fabricated zeroes), unavailable-database payload shape, metric
aggregation logic, recent-document bounds and deterministic ordering,
no-fabrication guarantees, and security-sensitive metadata filtering.

PostgreSQL-dependent aggregation lives in test_dashboard_api.py and skips
honestly without a database.
"""

from app.dashboard.service import (
    audit_metadata,
    build_recent_documents,
    compute_statuses,
    pure_document_metrics,
    pure_record_metrics,
    pure_validation_metrics,
)
from app.schemas.dashboard import DashboardSummary


def _doc_row(document_id=1, **overrides):
    row = {
        "document_id": document_id,
        "filename": f"doc{document_id}.pdf",
        "document_type": "pdf",
        "status": "processed",
        "validation_status": "pass",
        "extraction_status": "completed",
        "uploaded_at": None,
        "processed_at": None,
        "record_count": 3,
        "requires_review": False,
    }
    row.update(overrides)
    return row


# --- metric aggregation logic -------------------------------------------------


def test_document_metrics_aggregation():
    metrics = pure_document_metrics(
        {"processed": 3, "failed": 1, "uploaded": 2, "processing": 0}
    )
    assert metrics.total == 6
    assert metrics.processed == 3 and metrics.failed == 1
    assert metrics.by_status["processed"] == 3


def test_record_metrics_aggregation_and_status_rolls():
    metrics = pure_record_metrics(
        {"pass": 10, "pending": 4, "warning": 2, "error": 1, "review_required": 2}
    )
    assert metrics.total == 19
    assert metrics.validated == 10
    assert metrics.pending == 4
    assert metrics.flagged == 5  # warning + error + review_required


def test_validation_metrics_aggregation():
    metrics = pure_validation_metrics(
        {"pass": 8, "warning": 2, "error": 1, "review_required": 3}
    )
    assert metrics.total == 14
    assert metrics.review_required == 3
    assert metrics.errors == 1 and metrics.warnings == 2


def test_empty_selections_are_true_zeroes_not_missing():
    """Zero data IS distinguishable from offline (empty dict ⇒ zero counts)."""
    docs = pure_document_metrics({})
    assert docs.total == 0 and docs.by_status == {}
    records = pure_record_metrics({})
    assert records.total == 0
    validation = pure_validation_metrics({})
    assert validation.total == 0 and validation.review_required == 0


# --- honest status mapping (Phase 8) --------------------------------------------


def test_status_mapping_offline_is_unavailable_not_healthy():
    statuses = compute_statuses(
        db_connected=False, db_detail=None, index_stats=None, llm_configured=False
    )
    assert statuses["database"].status == "UNAVAILABLE"
    assert statuses["retrieval"].status == "UNAVAILABLE"
    assert statuses["embeddings"].status == "UNAVAILABLE"
    assert statuses["llm"].status == "NOT CONFIGURED"


def test_status_mapping_connected_states():
    empty = compute_statuses(db_connected=True, db_detail="connected",
                             index_stats={"total_units": 0, "embedded_units": 0},
                             llm_configured=True)
    assert empty["retrieval"].status == "DEGRADED"
    assert empty["embeddings"].status == "NOT CONFIGURED"
    assert empty["llm"].status == "OPERATIONAL"
    partial = compute_statuses(db_connected=True, db_detail="connected",
                               index_stats={"total_units": 10, "embedded_units": 4},
                               llm_configured=False)
    assert partial["retrieval"].status == "OPERATIONAL"
    assert partial["embeddings"].status == "DEGRADED"
    full = compute_statuses(db_connected=True, db_detail="connected",
                            index_stats={"total_units": 10, "embedded_units": 10},
                            llm_configured=False)
    assert full["embeddings"].status == "OPERATIONAL"


def test_llm_never_shown_operational_when_unconfigured():
    statuses = compute_statuses(db_connected=True, db_detail="connected",
                                index_stats={"total_units": 5, "embedded_units": 5},
                                llm_configured=False)
    assert statuses["llm"].status == "NOT CONFIGURED"


# --- recent documents: bounds, ordering, metadata-only ----------------------------


def test_recent_documents_bounded_to_eight():
    rows = [_doc_row(i, filename=f"paper_{i}.pdf") for i in range(1, 21)]
    items = build_recent_documents(rows)
    assert len(items) == 8
    assert items[0].document_id == 1 and items[-1].document_id == 8


def test_recent_documents_preserve_input_order_deterministically():
    rows = [_doc_row(i) for i in (5, 3, 9, 1)]
    items = build_recent_documents(rows)
    assert [item.document_id for item in items] == [5, 3, 9, 1]


def test_recent_documents_review_indicator_and_metadata_only():
    item = build_recent_documents([
        _doc_row(7, validation_status="review_required", requires_review=True,
                 filename="secret_mine_plan.pdf")
    ])[0]
    assert item.requires_review is True
    flat = item.model_dump_json()
    assert "storage" not in flat.lower() and "credential" not in flat.lower()


# --- schema round-trip + audit filtering --------------------------------------------


def test_dashboard_summary_schema_accepts_offline_payload():
    payload = {
        "data_available": False,
        "message": "Database unavailable — live operational metrics cannot be queried.",
        "database": {"component": "database", "status": "UNAVAILABLE"},
        "api": {"component": "api", "status": "OPERATIONAL"},
        "retrieval": {"component": "retrieval", "status": "UNAVAILABLE"},
        "embeddings": {"component": "embeddings", "status": "UNAVAILABLE"},
        "llm": {"component": "llm", "status": "NOT CONFIGURED"},
        "documents": None, "records": None, "validation": None,
        "knowledge": None, "intelligence": None,
        "recent_documents": [], "recent_activity": [],
        "limitations": ["read-only"],
    }
    summary = DashboardSummary(**payload)
    assert summary.data_available is False
    assert summary.documents is None
    assert summary.recent_documents == []


def test_dashboard_summary_schema_accepts_online_payload():
    payload = {
        "data_available": True,
        "database": {"component": "database", "status": "CONNECTED"},
        "api": {"component": "api", "status": "OPERATIONAL"},
        "retrieval": {"component": "retrieval", "status": "OPERATIONAL"},
        "embeddings": {"component": "embeddings", "status": "DEGRADED",
                       "detail": "4/10"},
        "llm": {"component": "llm", "status": "NOT CONFIGURED"},
        "documents": pure_document_metrics({"processed": 2}).model_dump(),
        "records": pure_record_metrics({"pass": 5}).model_dump(),
        "validation": pure_validation_metrics({"pass": 4, "error": 1}).model_dump(),
        "knowledge": {"total_units": 10, "pages": 5, "records": 3, "validations": 2,
                      "embedded_units": 4, "embedding_coverage": 0.4,
                      "documents_indexed": 1},
        "intelligence": {"available": True, "indexed_documents": 1,
                         "topic_count": 2, "top_topics": [{"topic_id": "t1", "label": "Coal / Production", "score": 3.0}],
                         "top_terms": [{"term": "coal", "display_term": "Coal", "frequency": 4}]},
        "recent_documents": [item.model_dump() for item in build_recent_documents([_doc_row(1)])],
        "recent_activity": [],
        "limitations": [],
    }
    summary = DashboardSummary(**payload)
    assert summary.data_available is True
    assert summary.documents.total == 2
    assert summary.intelligence.topic_count == 2


def test_audit_metadata_filters_contents():
    payload = {
        "data_available": True,
        "documents": {"total": 6}, "records": {"total": 17},
        "validation": {"review_required": 3},
        "intelligence": {"available": True},
        "recent_documents": [{"filename": "SECRET_PLAN.pdf"}],
        "recent_activity": [],
    }
    meta = audit_metadata(payload)
    flat = str(meta)
    assert "SECRET_PLAN" not in flat
    assert meta["document_total"] == 6
    assert meta["recent_document_count"] == 1


# --- no fabricated statistics ----------------------------------------------------------


def test_no_fabricated_statistics_in_pure_builders():
    """Builders only repackage provided counts — nothing is invented."""
    docs = pure_document_metrics({"processed": 2})
    assert docs.uploaded == 0 and docs.failed == 0  # absent ⇒ 0, not guessed
    records = pure_record_metrics({"pass": 3})
    assert records.flagged == 0 and records.pending == 0
    validation = pure_validation_metrics({"review_required": 1})
    assert validation.errors == 0 and validation.warnings == 0
