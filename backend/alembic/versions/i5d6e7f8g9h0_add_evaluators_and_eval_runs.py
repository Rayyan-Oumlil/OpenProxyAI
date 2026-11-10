"""Evaluators, eval runs and per-item results (Phase 3, slice 4). Org-scoped by RLS.

Revision ID: i5d6e7f8g9h0
Revises: h4c5d6e7f8g9
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "i5d6e7f8g9h0"
down_revision: Union[str, None] = "h4c5d6e7f8g9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORG_MATCH = "org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid"
_TABLES = ("evaluators", "eval_runs", "eval_run_items")


def _id() -> sa.Column:
    return sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()"))


def _org() -> sa.Column:
    return sa.Column("org_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "evaluators",
        _id(),
        _org(),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "name", name="uq_evaluators_org_name"),
        sa.CheckConstraint("type IN ('exact', 'regex', 'llm_judge')", name="ck_evaluators_type"),
    )
    op.create_table(
        "eval_runs",
        _id(),
        _org(),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("evaluator_id", sa.Uuid(), sa.ForeignKey("evaluators.id", ondelete="SET NULL"), nullable=True),
        sa.Column("evaluator_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("prompt_template_id", sa.Uuid(), sa.ForeignKey("prompt_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("candidate_model", sa.String(100), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score_sum", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("max_cost_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled', 'budget_exceeded')", name="ck_eval_runs_status"
        ),
    )
    op.create_index("ix_eval_runs_org_created", "eval_runs", ["org_id", "created_at"])
    op.create_table(
        "eval_run_items",
        _id(),
        _org(),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_item_id", sa.Uuid(), sa.ForeignKey("dataset_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("score", sa.Numeric(6, 4), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("run_id", "dataset_item_id", name="uq_eval_run_items_run_item"),
    )
    op.create_index("ix_eval_run_items_run_id", "eval_run_items", ["run_id"])
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY rls_org_isolation ON {table} FOR ALL USING ({_ORG_MATCH}) WITH CHECK ({_ORG_MATCH})")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user")


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP POLICY IF EXISTS rls_org_isolation ON {table}")
    op.drop_table("eval_run_items")
    op.drop_table("eval_runs")
    op.drop_table("evaluators")
