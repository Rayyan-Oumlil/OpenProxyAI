"""Let a score say where it came from, who sent it and why (feedback endpoint, Phase 3 slice 1).

Revision ID: f2a3b4c5d6e7
Revises: e1z2a3b4c5d6
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1z2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rows that exist today came from the console's JWT route, hence the default; new code sets it explicitly.
    op.add_column("request_scores", sa.Column("source", sa.String(20), nullable=False, server_default="console"))
    op.add_column("request_scores", sa.Column("comment", sa.Text(), nullable=True))
    op.add_column(
        "request_scores",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("request_scores", "user_id")
    op.drop_column("request_scores", "comment")
    op.drop_column("request_scores", "source")
