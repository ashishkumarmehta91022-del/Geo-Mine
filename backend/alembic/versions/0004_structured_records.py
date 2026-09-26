"""structured extraction fields + document validation status

Revision ID: 0004_structured_records
Revises: 0003_validation_review
Create Date: 2026-09-26

Step 7: extends (never replaces) the Step 2 extracted_records table so it can
represent structured data derived from raw extraction/OCR:
- value_raw: the verbatim source string ("1O5" stays "1O5")
- normalized_value: safely normalized value (NULL when not safely derivable)
- extraction_method: native_text | ocr | table | spreadsheet | docx
- record_metadata: provenance/evidence JSONB
- documents.validation_status: rollup of the latest validation run
Existing rows are preserved (backfilled with NULLs / explicit defaults).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_structured_records"
down_revision = "0003_validation_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("extracted_records", sa.Column("value_raw", sa.Text(), nullable=True))
    op.add_column("extracted_records", sa.Column("normalized_value", sa.String(length=256), nullable=True))
    op.add_column(
        "extracted_records",
        sa.Column("extraction_method", sa.String(length=32), nullable=False, server_default="native_text"),
    )
    op.add_column("extracted_records", sa.Column("record_metadata", postgresql.JSONB(), nullable=True))
    op.create_index("ix_extracted_records_extraction_method", "extracted_records", ["extraction_method"])

    op.add_column("documents", sa.Column("validation_status", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "validation_status")
    op.drop_index("ix_extracted_records_extraction_method", table_name="extracted_records")
    op.drop_column("extracted_records", "record_metadata")
    op.drop_column("extracted_records", "extraction_method")
    op.drop_column("extracted_records", "normalized_value")
    op.drop_column("extracted_records", "value_raw")
