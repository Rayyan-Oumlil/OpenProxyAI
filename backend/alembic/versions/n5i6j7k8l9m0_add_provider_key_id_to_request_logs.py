"""add provider_key_id to request_logs

Revision ID: n5i6j7k8l9m0
Revises: m4h5i6j7k8l9
Create Date: 2026-03-21

Nullable FK to llm_provider_keys for per-key adaptive load balancing.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "n5i6j7k8l9m0"
down_revision: Union[str, None] = "m4h5i6j7k8l9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "request_logs",
        sa.Column("provider_key_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_request_logs_provider_key_id",
        "request_logs",
        "llm_provider_keys",
        ["provider_key_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_request_logs_provider_key_id", "request_logs", type_="foreignkey")
    op.drop_column("request_logs", "provider_key_id")
