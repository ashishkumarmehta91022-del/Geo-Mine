"""Semantic embedding + retrieval integration tests — REQUIRE PostgreSQL.

Skip contract (conftest): without CMPDI_TEST_DATABASE_URL these tests skip
honestly — no SQLite substitute, no fake success. A deterministic fake
provider is injected via set_embedding_provider so these tests never depend
on model downloads; the real fastembed engine is smoke-verified separately.
"""

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.embeddings.base import EmbeddingProvider, EmbeddingResult
from app.embeddings.service import set_embedding_provider
from app.models import Document, ExtractedRecord, ValidationResult

pytestmark = pytest.mark.db


class FakeVectorProvider(EmbeddingProvider):
    """Deterministic 4-dim provider — same text ⇒ same vector, always."""

    name = "fake"
    model = "fake-model-v1"
    dimensions = 4

    def is_available(self) -> bool:
        return True

    def embed_batch(self, texts: list[str]) -> EmbeddingResult:
        vectors: list[list[float]] = []
        for t in texts:
            # Crude deterministic "semantics": length + keyword presence.
            base = float(len(t) % 13) / 13.0
            coal = 1.0 if "coal" in t.lower() else 0.0
            over = 1.0 if "overburden" in t.lower() else 0.0
            vec = [base, coal, over, 1.0]
            norm = sum(v * v for v in vec) ** 0.5 or 1.0
            vectors.append([v / norm for v in vec])
        return EmbeddingResult(
            vectors=vectors, provider=self.name, model=self.model, dimensions=self.dimensions
        )


class UnavailableVectorProvider(FakeVectorProvider):
    name = "unavailable"

    def is_available(self) -> bool:
        return False


@pytest.fixture(autouse=True)
def _fake_provider():
    """Inject the deterministic provider; restore the real singleton after."""
    from app.embeddings.service import get_embedding_provider

    real = get_embedding_provider()
    set_embedding_provider(FakeVectorProvider())
    yield
    set_embedding_provider(real)


def _session(migrated_engine) -> Session:
    return Session(migrated_engine)


def _make_document(migrated_engine, filename: str) -> int:
    """One processed document: a production record + a conflicting validation."""
    with _session(migrated_engine) as session:
        document = Document(
            filename=filename,
            document_type="xlsx",
            storage_reference=f"test/{filename}",
            status="processed",
        )
        session.add(document)
        session.flush()
        session.add(
            ExtractedRecord(
                document_id=document.id,
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
                validation_status="error",
            )
        )
        session.flush()
        session.add(
            ValidationResult(
                document_id=document.id,
                extracted_record_id=session.query(ExtractedRecord.id)
                .filter(ExtractedRecord.document_id == document.id)
                .scalar(),
                rule_code="RANGE_BOUNDARY",
                status="error",
                severity="warning",
                message="demo_coal_production 1200 exceeds expected upper bound (conflict)",
                source_reference="sheet Production, row 2",
            )
        )
        session.commit()
        return document.id


def _index_document(migrated_engine, document_id: int) -> None:
    from app.services.knowledge_service import index_document

    session = _session(migrated_engine)
    try:
        created = index_document(session, document_id)
        assert created >= 1
    finally:
        session.close()


def _embed_document(migrated_engine, document_id: int) -> dict:
    from app.services.knowledge_service import embed_document

    session = _session(migrated_engine)
    try:
        return embed_document(session, document_id)
    finally:
        session.close()


# --- schema / migration -----------------------------------------------------------------


def test_knowledge_index_has_embedding_columns(migrated_engine):
    inspector = sa_inspect(migrated_engine)
    columns = {c["name"]: c for c in inspector.get_columns("knowledge_index")}
    required = {
        "embedding",
        "embedding_provider",
        "embedding_model",
        "embedding_dimensions",
        "embedding_status",
        "embedding_error",
        "embedded_at",
    }
    missing = required - set(columns)
    assert not missing, f"migration 0006 columns missing: {sorted(missing)}"
    assert columns["embedding_status"]["nullable"] is False


def test_embedding_status_defaults_to_none(migrated_engine):
    document_id = _make_document(migrated_engine, "defaults.xlsx")
    with _session(migrated_engine) as session:
        session.execute(
            text(
                "INSERT INTO knowledge_index (unit_type, document_id, title, content) "
                "VALUES ('record', :did, 't', 'c')"
            ),
            {"did": document_id},
        )
        session.commit()
        row = session.execute(
            text("SELECT embedding_status FROM knowledge_index WHERE document_id = :did"),
            {"did": document_id},
        ).fetchone()
        assert row[0] == "none"


# --- embed_document lifecycle ------------------------------------------------------------


def test_embed_document_marks_rows_embedded_with_metadata(migrated_engine):
    document_id = _make_document(migrated_engine, "embed_me.xlsx")
    _index_document(migrated_engine, document_id)

    summary = _embed_document(migrated_engine, document_id)
    assert summary["embedded"] == summary["total"]
    assert summary["failed"] == 0
    assert summary["unavailable"] == 0

    with _session(migrated_engine) as session:
        rows = session.execute(
            text(
                "SELECT embedding_status, embedding_provider, embedding_model, "
                "embedding_dimensions, embedding, embedded_at FROM knowledge_index "
                "WHERE document_id = :did"
            ),
            {"did": document_id},
        ).fetchall()
        assert rows
        for status, provider, model, dims, vector, embedded_at in rows:
            assert status == "embedded"
            assert provider == "fake"
            assert model == "fake-model-v1"
            assert dims == 4
            assert len(vector) == 4
            assert all(-1.0001 <= v <= 1.0001 for v in vector)
            assert embedded_at is not None


def test_embed_document_idempotent_replacement(migrated_engine):
    document_id = _make_document(migrated_engine, "idempotent.xlsx")
    _index_document(migrated_engine, document_id)

    first = _embed_document(migrated_engine, document_id)
    second = _embed_document(migrated_engine, document_id)
    assert first["embedded"] == second["embedded"] == first["total"]

    with _session(migrated_engine) as session:
        count = session.execute(
            text("SELECT count(*) FROM knowledge_index WHERE document_id = :did"),
            {"did": document_id},
        ).scalar()
        assert count == first["total"]  # replaced in place, never duplicated


def test_embed_document_unavailable_provider_is_honest(migrated_engine):
    document_id = _make_document(migrated_engine, "offline.xlsx")
    _index_document(migrated_engine, document_id)
    set_embedding_provider(UnavailableVectorProvider())
    try:
        summary = _embed_document(migrated_engine, document_id)
        assert summary["unavailable"] == summary["total"]
        assert summary["embedded"] == 0
    finally:
        set_embedding_provider(FakeVectorProvider())

    with _session(migrated_engine) as session:
        rows = session.execute(
            text(
                "SELECT embedding_status, embedding_error FROM knowledge_index "
                "WHERE document_id = :did"
            ),
            {"did": document_id},
        ).fetchall()
        assert all(status == "unavailable" and error for status, error in rows)


def test_embed_document_missing_document_is_404(client):
    response = client.post("/api/search/embed/999999")
    assert response.status_code == 404


# --- semantic retrieval ------------------------------------------------------------------


def test_semantic_search_returns_provenance_and_similarity(client, migrated_engine):
    document_id = _make_document(migrated_engine, "semantic_prov.xlsx")
    _index_document(migrated_engine, document_id)
    _embed_document(migrated_engine, document_id)

    response = client.get("/api/search", params={"q": "coal production", "mode": "semantic"})
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "semantic"
    assert body["semantic_available"] is True
    assert body["total"] > 0
    for item in body["results"]:
        assert item["document_id"] == document_id
        assert item["semantic_similarity"] is not None
        assert -1.0 <= item["semantic_similarity"] <= 1.0
        assert "source_reference" in item and "extraction_method" in item
        assert "validation_status" in item


def test_semantic_search_respects_filters_and_pagination(client, migrated_engine):
    document_id = _make_document(migrated_engine, "semantic_filters.xlsx")
    _index_document(migrated_engine, document_id)
    _embed_document(migrated_engine, document_id)

    all_rows = client.get(
        "/api/search", params={"q": "coal", "mode": "semantic", "limit": 100}
    ).json()
    records = [r for r in all_rows["results"] if r["unit_type"] == "record"]
    assert records, "fixture must produce at least one record unit"
    target_entity = records[0]["entity"]

    filtered = client.get(
        "/api/search",
        params={"q": "coal", "mode": "semantic", "entity": target_entity, "limit": 100},
    ).json()
    assert filtered["total"] > 0
    assert all(r["entity"] == target_entity for r in filtered["results"])

    full = client.get(
        "/api/search", params={"q": "coal", "mode": "semantic", "limit": 100}
    ).json()
    paged = client.get(
        "/api/search", params={"q": "coal", "mode": "semantic", "limit": 1, "offset": 1}
    ).json()
    assert len(paged["results"]) <= 1
    if len(full["results"]) > 1:
        assert paged["results"][0]["document_id"] == full["results"][1]["document_id"]


def test_semantic_mode_without_provider_is_503(client, migrated_engine):
    document_id = _make_document(migrated_engine, "no_provider.xlsx")
    _index_document(migrated_engine, document_id)
    set_embedding_provider(UnavailableVectorProvider())
    try:
        response = client.get("/api/search", params={"q": "coal", "mode": "semantic"})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "semantic_unavailable"
    finally:
        set_embedding_provider(FakeVectorProvider())


def test_semantic_mode_requires_query_text(client, migrated_engine):
    response = client.get("/api/search", params={"mode": "semantic"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "empty_semantic_query"


def test_unsupported_mode_is_422(client):
    response = client.get("/api/search", params={"q": "coal", "mode": "vector-magic"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_mode"


# --- hybrid retrieval --------------------------------------------------------------------


def test_hybrid_search_merges_and_scores_transparently(client, migrated_engine):
    document_id = _make_document(migrated_engine, "hybrid.xlsx")
    _index_document(migrated_engine, document_id)
    _embed_document(migrated_engine, document_id)

    body = client.get("/api/search", params={"q": "coal production", "mode": "hybrid"}).json()
    assert body["mode"] == "hybrid"
    assert body["retrieval_note"], "hybrid must state that scores are not trust"
    assert body["total"] > 0

    lexical = client.get(
        "/api/search", params={"q": "coal production", "mode": "lexical", "limit": 100}
    ).json()
    semantic = client.get(
        "/api/search", params={"q": "coal production", "mode": "semantic", "limit": 100}
    ).json()
    # Union: every semantic hit must appear in hybrid results (same scope).
    hybrid_ids = {(r["document_id"], r["unit_type"]) for r in body["results"]}
    semantic_ids = {(r["document_id"], r["unit_type"]) for r in semantic["results"]}
    assert semantic_ids <= hybrid_ids
    assert body["total"] >= max(lexical["total"], semantic["total"])

    for item in body["results"]:
        assert item["relevance"] is not None, "hybrid rows carry the explicit combined score"


def test_hybrid_without_provider_falls_back_to_lexical(client, migrated_engine):
    document_id = _make_document(migrated_engine, "hybrid_fallback.xlsx")
    _index_document(migrated_engine, document_id)
    set_embedding_provider(UnavailableVectorProvider())
    try:
        response = client.get("/api/search", params={"q": "coal", "mode": "hybrid"})
        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "hybrid"
        assert body["semantic_available"] is False
        assert body["semantic_error"]
        assert body["total"] > 0  # lexical fallback actually returned data
        assert all(r["semantic_similarity"] is None for r in body["results"])
    finally:
        set_embedding_provider(FakeVectorProvider())


# --- conflicts / provenance preservation -------------------------------------------------


def test_conflicting_records_both_survive_semantic_and_hybrid(client, migrated_engine):
    """The validation conflict row keeps its status in every retrieval mode."""
    document_id = _make_document(migrated_engine, "conflicts.xlsx")
    _index_document(migrated_engine, document_id)
    _embed_document(migrated_engine, document_id)

    for mode in ("lexical", "semantic", "hybrid"):
        body = client.get("/api/search", params={"q": "coal", "mode": mode, "limit": 100}).json()
        validation_items = [r for r in body["results"] if r["unit_type"] == "validation"]
        assert validation_items, f"{mode}: conflict rows must stay retrievable"
        for item in validation_items:
            assert item["validation_id"] is not None
            assert item["validation_status"] == "error"
            # Similarity never rewrites validation state.
            assert item["validation_status"] != "pass"


# --- reprocessing / deletion lifecycle ---------------------------------------------------


def test_reprocessing_resets_and_reembeds(migrated_engine):
    """Reprocess flow: lexical delete-replace resets embedding state; re-embed
    recreates it (idempotent replace). Exercised at the service level because
    the full extractor pipeline is covered by Step 4–7 tests."""
    from app.services.knowledge_service import embed_document, index_document

    document_id = _make_document(migrated_engine, "reprocess.xlsx")
    _index_document(migrated_engine, document_id)
    _embed_document(migrated_engine, document_id)

    with _session(migrated_engine) as session:
        before = session.execute(
            text(
                "SELECT count(*), count(*) FILTER (WHERE embedding_status = 'embedded') "
                "FROM knowledge_index WHERE document_id = :did"
            ),
            {"did": document_id},
        ).fetchone()
        assert before[0] > 0 and before[1] == before[0]

        # Simulate reprocessing's delete-replace of derived index rows.
        session.execute(
            text("DELETE FROM knowledge_index WHERE document_id = :did"), {"did": document_id}
        )
        session.commit()

        # Lexical reindex (the Step 8 path used by reprocessing).
        created = index_document(session, document_id)
        assert created > 0

        statuses = session.execute(
            text(
                "SELECT DISTINCT embedding_status FROM knowledge_index "
                "WHERE document_id = :did"
            ),
            {"did": document_id},
        ).fetchall()
        assert [r[0] for r in statuses] == ["none"], "replaced rows must start unstale"

        summary = embed_document(session, document_id)
        assert summary["embedded"] == summary["total"]

        again = embed_document(session, document_id)
        assert again["embedded"] == again["total"] == summary["total"]


def test_document_deletion_removes_semantic_entries(client, migrated_engine):
    document_id = _make_document(migrated_engine, "deleted.xlsx")
    _index_document(migrated_engine, document_id)
    _embed_document(migrated_engine, document_id)

    with _session(migrated_engine) as session:
        embedded = session.execute(
            text(
                "SELECT count(*) FROM knowledge_index "
                "WHERE document_id = :did AND embedding_status = 'embedded'"
            ),
            {"did": document_id},
        ).scalar()
        assert embedded > 0

    response = client.delete(f"/api/documents/{document_id}")
    assert response.status_code in (200, 204)

    with _session(migrated_engine) as session:
        remaining = session.execute(
            text("SELECT count(*) FROM knowledge_index WHERE document_id = :did"),
            {"did": document_id},
        ).scalar()
        assert remaining == 0, "cascade must remove embedded rows too"
