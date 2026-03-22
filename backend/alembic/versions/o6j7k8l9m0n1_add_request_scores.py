"""add request_scores table for experiment quality scoring

Revision ID: o6j7k8l9m0n1
Revises: n5i6j7k8l9m0
Create Date: 2026-03-21

Quality scores per request for LLM-as-judge and experiment evaluation.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "o6j7k8l9m0n1"
down_revision: Union[str, None] = "n5i6j7k8l9m0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "request_scores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=True),
        sa.Column("variant_id", sa.Uuid(), nullable=True),
        sa.Column("score_name", sa.String(100), nullable=False),
        sa.Column("value", sa.Numeric(10, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variant_id"], ["experiment_variants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_request_scores_request_org",
        "request_scores",
        ["request_id", "org_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_request_scores_request_name",
        "request_scores",
        ["request_id", "score_name"],
    )
    op.create_index(
        "idx_request_scores_experiment_variant",
        "request_scores",
        ["experiment_id", "variant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_request_scores_experiment_variant", table_name="request_scores")
    op.drop_constraint("uq_request_scores_request_name", "request_scores", type_="unique")
    op.drop_index("idx_request_scores_request_org", table_name="request_scores")
    op.drop_table("request_scores")
