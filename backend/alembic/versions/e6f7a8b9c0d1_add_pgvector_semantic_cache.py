"""add pgvector semantic cache

Revision ID: e6f7a8b9c0d1
Revises: c3d4e5f6a7b8
Create Date: 2026-03-19

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "e6f7a8b9c0d1"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "semantic_cache_entries",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("messages_hash", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("response_json", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_semantic_cache_org_model",
        "semantic_cache_entries",
        ["org_id", "model"],
        unique=False,
    )
    op.execute(
        "CREATE INDEX idx_semantic_cache_embedding ON semantic_cache_entries "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.drop_index("idx_semantic_cache_embedding", table_name="semantic_cache_entries")
    op.drop_index("idx_semantic_cache_org_model", table_name="semantic_cache_entries")
    op.drop_table("semantic_cache_entries")
    op.execute("DROP EXTENSION IF EXISTS vector")
