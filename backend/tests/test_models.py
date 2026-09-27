"""Model/migration integrity tests (no PostgreSQL required).

These verify the SQLAlchemy metadata that Alembic migrations are generated
from and that the initial migration mirrors.
"""

from sqlalchemy import inspect
from sqlalchemy.schema import DropTable, CreateTable

from app.db import engine
from app.models import (
    AuditLog,
    Base,
    Document,
    DocumentPage,
    ExtractedRecord,
    ValidationResult,
)

EXPECTED_TABLES = {
    "documents",
    "document_pages",
    "extracted_records",
    "validation_results",
    "audit_logs",
    "knowledge_index",  # Step 8: retrieval layer (not a source of truth)
}


def _columns(model):
    return {c.name for c in model.__table__.columns}


def test_all_foundation_tables_registered():
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_document_columns_present():
    cols = _columns(Document)
    assert {
        "id", "filename", "document_type", "source", "storage_reference",
        "status", "uploaded_at", "processed_at", "created_at", "updated_at",
    } <= cols


def test_document_page_columns_and_unique_constraint():
    page_table = DocumentPage.__table__
    assert {"id", "document_id", "page_number", "extracted_text", "processing_status", "created_at"} <= _columns(DocumentPage)
    unique_pairs = [
        {col.name for col in constraint.columns}
        for constraint in page_table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    ]
    assert {"document_id", "page_number"} in unique_pairs


def test_extracted_record_nullable_relationships():
    cols = _columns(ExtractedRecord)
    assert "page_id" in cols
    page_id_col = ExtractedRecord.__table__.columns["page_id"]
    assert page_id_col.nullable is True  # records may exist without a specific page
    assert page_id_col.foreign_keys, "page_id must reference document_pages"


def test_validation_result_references_extracted_record():
    fk = ValidationResult.__table__.columns["extracted_record_id"].foreign_keys
    assert any(k.column.table.name == "extracted_records" for k in fk)


def test_validation_result_supports_page_level_results():
    """Step 6: OCR/page-level checks exist without an extracted record."""
    record_col = ValidationResult.__table__.columns["extracted_record_id"]
    assert record_col.nullable is True
    assert "document_id" in ValidationResult.__table__.columns
    assert "page_id" in ValidationResult.__table__.columns
    assert {"severity", "review_status", "rule_code", "details"} <= _columns(ValidationResult)


def test_audit_log_uses_entity_reference_columns():
    cols = _columns(AuditLog)
    assert {"entity_type", "entity_id", "action", "details", "created_at"} <= cols


def test_relationship_chains():
    def target_tables(model):
        return {rel.mapper.class_.__tablename__ for rel in inspect(model).relationships}

    # documents -> document_pages
    assert "document_pages" in target_tables(Document)
    # documents -> extracted_records
    assert "extracted_records" in target_tables(Document)
    # document_pages -> documents (via document_id FK)
    assert any(fk.column.table.name == "documents" for fk in DocumentPage.__table__.columns["document_id"].foreign_keys)
    # extracted_records -> validation_results
    assert "validation_results" in target_tables(ExtractedRecord)


def test_key_indexes_exist():
    extracted_indexes = {i.name for i in ExtractedRecord.__table__.indexes}
    document_indexes = {i.name for i in Document.__table__.indexes}
    assert {"ix_extracted_records_entity_name", "ix_extracted_records_metric_name",
            "ix_extracted_records_reporting_period"} <= extracted_indexes
    assert {"ix_documents_filename", "ix_documents_document_type"} <= document_indexes


def test_migration_revisions_chain():
    """The migration chain 0001 → 0002 → 0003 is the schema source of truth."""
    import ast
    from pathlib import Path

    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    revisions = {}
    for path in versions_dir.glob("*.py"):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rev = down = None
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "revision":
                        rev = ast.literal_eval(node.value)
                    if isinstance(target, ast.Name) and target.id == "down_revision":
                        down = ast.literal_eval(node.value)
        revisions[rev] = down

    assert revisions["0001_initial_schema"] is None  # single root migration
    assert revisions["0002_extraction_columns"] == "0001_initial_schema"
    assert revisions["0003_validation_review"] == "0002_extraction_columns"
    assert revisions["0004_structured_records"] == "0003_validation_review"
    assert revisions["0005_knowledge_index"] == "0004_structured_records"
    assert revisions["0006_semantic_embeddings"] == "0005_knowledge_index"


def test_metadata_matches_initial_migration_ddl():
    """Cross-check migrations against model metadata: every table is created
    by SOME migration in the chain (0001 for the foundation, later migrations
    for layers added in Steps 5–8)."""
    from pathlib import Path

    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    all_migration_ddl = "\n".join(
        path.read_text(encoding="utf-8")
        for path in versions_dir.glob("*.py")
        if path.name != "__init__.py"
    )

    for table in EXPECTED_TABLES:
        assert f'"{table}"' in all_migration_ddl, f"no migration creates {table}"


def test_create_all_ddl_is_clean_sql():
    """Sanity check: metadata can compile CREATE TABLE statements for PostgreSQL."""
    ddl = str(CreateTable(Document.__table__).compile(dialect=engine.dialect))
    assert "CREATE TABLE documents" in ddl
    assert DropTable  # imported to prove dialect-aware compilation imports work
