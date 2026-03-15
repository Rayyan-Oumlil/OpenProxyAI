"""add_user_invites

Revision ID: d4e7f12a9c3b
Revises: c4f9a12e8b7d
Create Date: 2026-03-15 12:00:00.000000

Creates the user_invites table for the team invite system.
Stores SHA-256 token hashes so raw tokens are never persisted.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e7f12a9c3b"
down_revision: Union[str, None] = "c4f9a12e8b7d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_invites",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), server_default="developer", nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("invited_by", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('admin', 'developer', 'viewer')",
            name="ck_user_invites_role_valid",
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "idx_user_invites_org_pending",
        "user_invites",
        ["org_id", "accepted_at", "expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_invites_token_hash"),
        "user_invites",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_invites_token_hash"), table_name="user_invites")
    op.drop_index("idx_user_invites_org_pending", table_name="user_invites")
    op.drop_table("user_invites")
