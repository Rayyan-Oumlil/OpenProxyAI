"""Files and batches (Phase 5, slice 5.6). Org-scoped by RLS.

Revision ID: p2k3l4m5n6o7
Revises: o1j2k3l4m5n6
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "p2k3l4m5n6o7"
down_revision: Union[str, None] = "o1j2k3l4m5n6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORG_MATCH = "org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid"
_TABLES = ("batch_files", "batch_jobs", "batch_results")


def _org() -> sa.Column:
    return sa.Column("org_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "batch_files",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        _org(),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("purpose", sa.String(10), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("line_count", sa.Integer(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("purpose IN ('batch', 'output')", name="ck_batch_files_purpose"),
        sa.CheckConstraint("size_bytes >= 0 AND size_bytes <= 16777216", name="ck_batch_files_size"),
    )
    op.create_index("ix_batch_files_user", "batch_files", ["org_id", "user_id", "created_at"])
    op.create_index("ix_batch_files_expires", "batch_files", ["expires_at"])
    op.create_table(
        "batch_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        _org(),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("input_file_id", sa.Uuid(), sa.ForeignKey("batch_files.id", ondelete="SET NULL"), nullable=True),
        sa.Column("output_file_id", sa.Uuid(), sa.ForeignKey("batch_files.id", ondelete="SET NULL"), nullable=True),
        sa.Column("endpoint", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="validating"),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("max_cost_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('validating', 'in_progress', 'completed', 'failed', 'cancelled', 'budget_exceeded')", name="ck_batch_jobs_status"
        ),
    )
    op.create_index("ix_batch_jobs_org_created", "batch_jobs", ["org_id", "created_at"])
    op.create_table(
        "batch_results",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        _org(),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("batch_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("custom_id", sa.String(64), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("body", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.UniqueConstraint("job_id", "idx", name="uq_batch_results_job_idx"),
    )
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY rls_org_isolation ON {table} FOR ALL USING ({_ORG_MATCH}) WITH CHECK ({_ORG_MATCH})")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user")


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP POLICY IF EXISTS rls_org_isolation ON {table}")
    op.drop_table("batch_results")
    op.drop_table("batch_jobs")
    op.drop_table("batch_files")
