"""add team_id to api_keys

Revision ID: m4h5i6j7k8l9
Revises: l3g4h5i6j7k8
Create Date: 2026-03-20

Optional team_id on gateway API keys for team-scoped cost attribution.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "m4h5i6j7k8l9"
down_revision: Union[str, None] = "l3g4h5i6j7k8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column("team_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_api_keys_team_id",
        "api_keys",
        "teams",
        ["team_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_api_keys_team_id", "api_keys", type_="foreignkey")
    op.drop_column("api_keys", "team_id")
