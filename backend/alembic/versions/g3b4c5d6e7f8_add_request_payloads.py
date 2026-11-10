"""Opt-in storage of redacted prompts and answers, for evaluation (Phase 3, slice 2). Org-scoped by RLS.

Revision ID: g3b4c5d6e7f8
Revises: f2a3b4c5d6e7
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "g3b4c5d6e7f8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORG_MATCH = "org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "request_payloads",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("messages", postgresql.JSONB(), nullable=False),
        sa.Column("output", sa.Text(), nullable=False),
        sa.Column("redacted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "request_id", name="uq_request_payloads_org_request"),
    )
    op.create_index("ix_request_payloads_expires_at", "request_payloads", ["expires_at"])
    op.execute("ALTER TABLE request_payloads ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE request_payloads FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY rls_org_isolation ON request_payloads FOR ALL USING ({_ORG_MATCH}) WITH CHECK ({_ORG_MATCH})")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON request_payloads TO app_user")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS rls_org_isolation ON request_payloads")
    op.drop_table("request_payloads")
