"""validation engine + review workflow columns

Revision ID: 0003_validation_review
Revises: 0002_extraction_columns
Create Date: 2026-09-26

Step 6: extends (not duplicates) the existing validation_results table:
- document_id anchor (NOT NULL after backfill) so page/OCR-level checks can
  exist without an extracted record
- page_id link, severity, review workflow columns, structured details
- extracted_record_id becomes nullable (OCR/page-level results)
- rule_code: rename of validation_type (same data, clearer name)
Existing rows are preserved and backfilled.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_validation_review"
down_revision = "0002_extraction_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- new columns ---------------------------------------------------------
    op.add_column("validation_results", sa.Column("document_id", sa.Integer(), nullable=True))
    op.add_column("validation_results", sa.Column("page_id", sa.Integer(), nullable=True))
    op.add_column(
        "validation_results",
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="warning"),
    )
    op.add_column(
        "validation_results",
        sa.Column("review_status", sa.String(length=16), nullable=False, server_default="open"),
    )
    op.add_column("validation_results", sa.Column("review_notes", sa.Text(), nullable=True))
    op.add_column("validation_results", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("validation_results", sa.Column("details", postgresql.JSONB(), nullable=True))

    # --- backfill document anchor from linked records (preserves existing data) ---
    op.execute(
        """
        UPDATE validation_results AS v
        SET document_id = er.document_id
        FROM extracted_records AS er
        WHERE v.extracted_record_id = er.id
        """
    )
    op.alter_column("validation_results", "document_id", existing_type=sa.Integer(), nullable=False)

    # --- rename validation_type -> rule_code (clearer; same data) ---
    op.alter_column(
        "validation_results",
        "validation_type",
        new_column_name="rule_code",
        existing_type=sa.String(length=64),
        existing_nullable=False,
    )

    # --- OCR/page-level results may exist without an extracted record ---
    op.alter_column("validation_results", "extracted_record_id", existing_type=sa.Integer(), nullable=True)

    # --- relationships + query-supporting indexes ---
    op.create_foreign_key(
        "fk_validation_results_document_id_documents",
        "validation_results",
        "documents",
        ["document_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_validation_results_page_id_document_pages",
        "validation_results",
        "document_pages",
        ["page_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_validation_results_document_id", "validation_results", ["document_id"])
    op.create_index("ix_validation_results_status", "validation_results", ["status"])
    op.create_index("ix_validation_results_severity", "validation_results", ["severity"])
    op.create_index("ix_validation_results_review_status", "validation_results", ["review_status"])
    op.create_index("ix_validation_results_rule_code", "validation_results", ["rule_code"])


def downgrade() -> None:
    op.drop_index("ix_validation_results_rule_code", table_name="validation_results")
    op.drop_index("ix_validation_results_review_status", table_name="validation_results")
    op.drop_index("ix_validation_results_severity", table_name="validation_results")
    op.drop_index("ix_validation_results_status", table_name="validation_results")
    op.drop_index("ix_validation_results_document_id", table_name="validation_results")
    op.drop_constraint("fk_validation_results_page_id_document_pages", "validation_results", type_="foreignkey")
    op.drop_constraint("fk_validation_results_document_id_documents", "validation_results", type_="foreignkey")

    # Old schema required a record link; drop results that cannot satisfy it.
    op.execute("DELETE FROM validation_results WHERE extracted_record_id IS NULL")
    op.alter_column("validation_results", "extracted_record_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column(
        "validation_results",
        "rule_code",
        new_column_name="validation_type",
        existing_type=sa.String(length=64),
        existing_nullable=False,
    )
    op.drop_column("validation_results", "details")
    op.drop_column("validation_results", "reviewed_at")
    op.drop_column("validation_results", "review_notes")
    op.drop_column("validation_results", "review_status")
    op.drop_column("validation_results", "severity")
    op.drop_column("validation_results", "page_id")
    op.drop_column("validation_results", "document_id")
