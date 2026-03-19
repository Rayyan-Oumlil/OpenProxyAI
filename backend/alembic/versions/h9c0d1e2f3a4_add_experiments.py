"""add experiments and experiment_variants for A/B testing

Revision ID: h9c0d1e2f3a4
Revises: g8b9c0d1e2f3
Create Date: 2026-03-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h9c0d1e2f3a4"
down_revision: Union[str, None] = "g8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("target_model", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_experiments_org_target_active",
        "experiments",
        ["org_id", "target_model", "is_active"],
        unique=False,
    )

    op.create_table(
        "experiment_variants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("traffic_weight", sa.Integer(), nullable=False, server_default="50"),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_experiment_variants_experiment_id",
        "experiment_variants",
        ["experiment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_experiment_variants_experiment_id", table_name="experiment_variants")
    op.drop_table("experiment_variants")
    op.drop_index("idx_experiments_org_target_active", table_name="experiments")
    op.drop_table("experiments")
