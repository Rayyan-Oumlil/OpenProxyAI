"""add_webhook_deliveries

Revision ID: a2b3c4d5e6f7
Revises: f1a9c3e7d5b2
Create Date: 2026-03-15 16:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "f1a9c3e7d5b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "webhook_deliveries",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("last_attempted_at", sa.DateTime(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_webhook_deliveries_org_created",
        "webhook_deliveries",
        ["org_id", "created_at"],
    )
    op.create_index(
        "idx_webhook_deliveries_status",
        "webhook_deliveries",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("idx_webhook_deliveries_status", table_name="webhook_deliveries")
    op.drop_index("idx_webhook_deliveries_org_created", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
