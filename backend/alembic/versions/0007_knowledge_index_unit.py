"""persist knowledge_index.unit (embedding context)

Revision ID: 0007_knowledge_index_unit
Revises: 0006_semantic_embeddings
Create Date: 2026-09-28

Runtime recovery fix (local PostgreSQL bring-up): IndexUnitDraft carries the
record unit of measure (`unit`) as embedding-input context, but it was never
persisted — so re-embedding stored rows crashed
(`'KnowledgeIndex' object has no attribute 'unit'`) and could not rebuild
inputs identical to first-index inputs. Add the nullable column (same
type/length as extracted_records.unit) so drafts round-trip losslessly.
Additive and backward-compatible; existing rows keep NULL until re-indexed.
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_knowledge_index_unit"
down_revision = "0006_semantic_embeddings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_index",
        sa.Column("unit", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_index", "unit")
