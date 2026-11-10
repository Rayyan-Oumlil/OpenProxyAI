"""Adaptive A/B experiments (Phase 3, slice 5): shift traffic toward the better variant and stop when it is clear.

Revision ID: j6e7f8g9h0i1
Revises: i5d6e7f8g9h0
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j6e7f8g9h0i1"
down_revision: Union[str, None] = "i5d6e7f8g9h0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("experiments", sa.Column("mode", sa.String(10), nullable=False, server_default="static"))
    op.add_column("experiments", sa.Column("metric", sa.String(100), nullable=True))
    op.add_column("experiments", sa.Column("min_samples_per_variant", sa.Integer(), nullable=False, server_default="30"))
    op.add_column("experiments", sa.Column("delta", sa.Numeric(5, 4), nullable=False, server_default="0.0100"))
    op.add_column("experiments", sa.Column("weight_floor", sa.Integer(), nullable=False, server_default="5"))
    op.add_column(
        "experiments",
        sa.Column("winner_variant_id", sa.Uuid(), sa.ForeignKey("experiment_variants.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column("experiments", sa.Column("stopped_reason", sa.String(20), nullable=True))
    op.add_column("experiments", sa.Column("adaptive_error", sa.Text(), nullable=True))
    op.add_column("experiments", sa.Column("adaptive_updated_at", sa.DateTime(), nullable=True))
    op.create_check_constraint("ck_experiments_mode", "experiments", "mode IN ('static', 'adaptive')")
    op.create_check_constraint("ck_experiments_min_samples", "experiments", "min_samples_per_variant >= 20")
    op.create_check_constraint("ck_experiments_delta", "experiments", "delta > 0 AND delta < 1")
    op.create_check_constraint("ck_experiments_floor", "experiments", "weight_floor BETWEEN 1 AND 20")
    op.create_check_constraint("ck_experiments_stopped_reason", "experiments", "stopped_reason IS NULL OR stopped_reason IN ('winner', 'manual')")
    op.create_check_constraint("ck_experiments_adaptive_metric", "experiments", "mode = 'static' OR metric IS NOT NULL")


def downgrade() -> None:
    for name in ("ck_experiments_adaptive_metric", "ck_experiments_stopped_reason", "ck_experiments_floor", "ck_experiments_delta",
                 "ck_experiments_min_samples", "ck_experiments_mode"):
        op.drop_constraint(name, "experiments", type_="check")
    for column in ("adaptive_updated_at", "adaptive_error", "stopped_reason", "winner_variant_id", "weight_floor", "delta",
                   "min_samples_per_variant", "metric", "mode"):
        op.drop_column("experiments", column)
