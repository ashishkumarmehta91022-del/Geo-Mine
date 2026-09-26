"""knowledge base retrieval index (Step 8)

Revision ID: 0005_knowledge_index
Revises: 0004_structured_records
Create Date: 2026-09-26

Retrieval/index layer over the authoritative source tables. Deleting a
document cascades to its index entries (no orphaned search results);
reprocessing replaces a document's entries idempotently in service code.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_knowledge_index"
down_revision = "0004_structured_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_index",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", name="fk_knowledge_index_document_id_documents", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_id", sa.Integer(), nullable=True),
        sa.Column("record_id", sa.Integer(), nullable=True),
        sa.Column("validation_id", sa.Integer(), nullable=True),
        # page | record | validation — which retrieval unit this row represents.
        sa.Column("unit_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("source_reference", sa.String(length=512), nullable=True),
        sa.Column("entity", sa.String(length=256), nullable=True),
        sa.Column("metric", sa.String(length=128), nullable=True),
        sa.Column("reporting_period", sa.String(length=64), nullable=True),
        sa.Column("extraction_method", sa.String(length=32), nullable=True),
        sa.Column("validation_status", sa.String(length=32), nullable=True),
        sa.Column("ocr_confidence", sa.Numeric(5, 4), nullable=True),
        # PostgreSQL-native full-text search vector (updated by the service).
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_knowledge_index_document_id", "knowledge_index", ["document_id"])
    op.create_index("ix_knowledge_index_unit_type", "knowledge_index", ["unit_type"])
    op.create_index("ix_knowledge_index_entity", "knowledge_index", ["entity"])
    op.create_index("ix_knowledge_index_metric", "knowledge_index", ["metric"])
    op.create_index("ix_knowledge_index_validation_status", "knowledge_index", ["validation_status"])
    # GIN index for full-text search.
    op.create_index(
        "ix_knowledge_index_search_vector",
        "knowledge_index",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_index_search_vector", table_name="knowledge_index")
    op.drop_index("ix_knowledge_index_validation_status", table_name="knowledge_index")
    op.drop_index("ix_knowledge_index_metric", table_name="knowledge_index")
    op.drop_index("ix_knowledge_index_entity", table_name="knowledge_index")
    op.drop_index("ix_knowledge_index_unit_type", table_name="knowledge_index")
    op.drop_index("ix_knowledge_index_document_id", table_name="knowledge_index")
    op.drop_table("knowledge_index")
