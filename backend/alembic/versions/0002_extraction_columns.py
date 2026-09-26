"""extraction provenance columns for documents and document_pages

Revision ID: 0002_extraction_columns
Revises: 0001_initial_schema
Create Date: 2026-09-26

Step 4: adds extractor metadata and per-unit extraction status to the
existing tables (schema change only — no new tables, reusing Step 2 models
as instructed). Safe on empty or populated databases.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_extraction_columns"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("extraction_status", sa.String(length=32), nullable=True))
    op.add_column("documents", sa.Column("extractor_name", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("extractor_version", sa.String(length=32), nullable=True))
    op.add_column("documents", sa.Column("error_message", sa.Text(), nullable=True))

    op.add_column("document_pages", sa.Column("content_type", sa.String(length=32), nullable=False, server_default="page"))
    op.add_column("document_pages", sa.Column("section_reference", sa.String(length=256), nullable=True))
    op.add_column("document_pages", sa.Column("extraction_status", sa.String(length=32), nullable=False, server_default="pending"))
    op.add_column("document_pages", sa.Column("extractor_name", sa.String(length=64), nullable=True))
    op.add_column("document_pages", sa.Column("extractor_version", sa.String(length=32), nullable=True))
    op.add_column("document_pages", sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("document_pages", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("document_pages", sa.Column("structured_metadata", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("document_pages", "structured_metadata")
    op.drop_column("document_pages", "error_message")
    op.drop_column("document_pages", "extracted_at")
    op.drop_column("document_pages", "extractor_version")
    op.drop_column("document_pages", "extractor_name")
    op.drop_column("document_pages", "extraction_status")
    op.drop_column("document_pages", "section_reference")
    op.drop_column("document_pages", "content_type")

    op.drop_column("documents", "extractor_version")
    op.drop_column("documents", "extractor_name")
    op.drop_column("documents", "extraction_status")
    op.drop_column("documents", "error_message")
