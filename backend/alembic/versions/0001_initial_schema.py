"""initial schema: documents, document_pages, extracted_records, validation_results, audit_logs

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-26

Foundation tables for the CMPDI/CIL reporting platform. Later steps
(OCR/extraction/validation) will extend the schema via new migrations —
this migration stays the source of truth for the base schema.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

NOW = sa.text("now()")


def upgrade() -> None:
    # --- documents ---------------------------------------------------------
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False, server_default="upload"),
        sa.Column("storage_reference", sa.String(length=1024), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="uploaded"),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
    )
    op.create_index("ix_documents_filename", "documents", ["filename"])
    op.create_index("ix_documents_document_type", "documents", ["document_type"])

    # --- document_pages ----------------------------------------------------
    op.create_table(
        "document_pages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", name="fk_document_pages_document_id_documents", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("processing_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.UniqueConstraint("document_id", "page_number", name="uq_document_pages_doc_page"),
    )
    op.create_index("ix_document_pages_document_id", "document_pages", ["document_id"])

    # --- extracted_records --------------------------------------------------
    op.create_table(
        "extracted_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", name="fk_extracted_records_document_id_documents", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "page_id",
            sa.Integer(),
            sa.ForeignKey("document_pages.id", name="fk_extracted_records_page_id_document_pages", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("record_type", sa.String(length=64), nullable=False),
        sa.Column("entity_name", sa.String(length=256), nullable=False),
        sa.Column("metric_name", sa.String(length=128), nullable=False),
        sa.Column("metric_value", sa.Numeric(20, 4), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("reporting_period", sa.String(length=64), nullable=True),
        sa.Column("source_reference", sa.String(length=512), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("validation_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
    )
    op.create_index("ix_extracted_records_document_id", "extracted_records", ["document_id"])
    op.create_index("ix_extracted_records_entity_name", "extracted_records", ["entity_name"])
    op.create_index("ix_extracted_records_metric_name", "extracted_records", ["metric_name"])
    op.create_index("ix_extracted_records_reporting_period", "extracted_records", ["reporting_period"])
    op.create_index("ix_extracted_records_validation_status", "extracted_records", ["validation_status"])

    # --- validation_results --------------------------------------------------
    op.create_table(
        "validation_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "extracted_record_id",
            sa.Integer(),
            sa.ForeignKey(
                "extracted_records.id",
                name="fk_validation_results_extracted_record_id_extracted_records",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column("validation_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("expected_value", sa.String(length=256), nullable=True),
        sa.Column("actual_value", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
    )
    op.create_index("ix_validation_results_extracted_record_id", "validation_results", ["extracted_record_id"])

    # --- audit_logs -----------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
    )
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("validation_results")
    op.drop_table("extracted_records")
    op.drop_table("document_pages")
    op.drop_table("documents")
