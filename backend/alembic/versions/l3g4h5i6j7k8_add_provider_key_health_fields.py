"""add provider key health check fields

Revision ID: l3g4h5i6j7k8
Revises: k2f3a4b5c6d7
Create Date: 2026-03-20

Adds last_health_check_at, health_status, consecutive_failures for provider health check job.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l3g4h5i6j7k8"
down_revision: Union[str, None] = "k2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "llm_provider_keys",
        sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "llm_provider_keys",
        sa.Column(
            "health_status",
            sa.String(20),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column(
        "llm_provider_keys",
        sa.Column(
            "consecutive_failures",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_check_constraint(
        "ck_provider_keys_health_status",
        "llm_provider_keys",
        "health_status IN ('healthy', 'unhealthy', 'unknown')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_provider_keys_health_status",
        "llm_provider_keys",
        type_="check",
    )
    op.drop_column("llm_provider_keys", "consecutive_failures")
    op.drop_column("llm_provider_keys", "health_status")
    op.drop_column("llm_provider_keys", "last_health_check_at")
