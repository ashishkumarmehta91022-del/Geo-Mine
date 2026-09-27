"""semantic embeddings on knowledge_index (Step 9)

Revision ID: 0006_semantic_embeddings
Revises: 0005_knowledge_index
Create Date: 2026-09-26

Step 9 extends the Step 8 retrieval layer with semantic vectors:
- embedding: JSONB float array (pgvector-free storage; a later migration can
  convert to pgvector's vector type when PostgreSQL+pgvector are available)
- embedding_provider / embedding_model / embedding_dimensions: reproducibility
- embedding_status: none | pending | embedded | failed | unavailable
- embedding_error: honest failure reason
- embedded_at
No source-of-truth table is modified; document deletion still cascades.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_semantic_embeddings"
down_revision = "0005_knowledge_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_index", sa.Column("embedding", postgresql.JSONB(), nullable=True))
    op.add_column("knowledge_index", sa.Column("embedding_provider", sa.String(length=64), nullable=True))
    op.add_column("knowledge_index", sa.Column("embedding_model", sa.String(length=128), nullable=True))
    op.add_column("knowledge_index", sa.Column("embedding_dimensions", sa.Integer(), nullable=True))
    op.add_column(
        "knowledge_index",
        sa.Column("embedding_status", sa.String(length=16), nullable=False, server_default="none"),
    )
    op.add_column("knowledge_index", sa.Column("embedding_error", sa.Text(), nullable=True))
    op.add_column("knowledge_index", sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_knowledge_index_embedding_status", "knowledge_index", ["embedding_status"]
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_index_embedding_status", table_name="knowledge_index")
    op.drop_column("knowledge_index", "embedded_at")
    op.drop_column("knowledge_index", "embedding_error")
    op.drop_column("knowledge_index", "embedding_status")
    op.drop_column("knowledge_index", "embedding_dimensions")
    op.drop_column("knowledge_index", "embedding_model")
    op.drop_column("knowledge_index", "embedding_provider")
    op.drop_column("knowledge_index", "embedding")
