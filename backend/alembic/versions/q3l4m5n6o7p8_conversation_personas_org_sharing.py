"""Conversation personas, org-wide sharing and the log_only preview (Phase 4 follow-up).

Revision ID: q3l4m5n6o7p8
Revises: p2k3l4m5n6o7
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "q3l4m5n6o7p8"
down_revision: Union[str, None] = "p2k3l4m5n6o7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("system_prompt", sa.Text(), nullable=True))
    op.drop_constraint("ck_conversations_visibility", "conversations", type_="check")
    op.create_check_constraint("ck_conversations_visibility", "conversations", "visibility IN ('private', 'team', 'org')")
    op.add_column(
        "conversation_context_packages",
        sa.Column("would_withhold", postgresql.JSONB(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("conversation_context_packages", "would_withhold")
    op.execute("UPDATE conversations SET visibility = 'private' WHERE visibility = 'org'")
    op.drop_constraint("ck_conversations_visibility", "conversations", type_="check")
    op.create_check_constraint("ck_conversations_visibility", "conversations", "visibility IN ('private', 'team')")
    op.drop_column("conversations", "system_prompt")
