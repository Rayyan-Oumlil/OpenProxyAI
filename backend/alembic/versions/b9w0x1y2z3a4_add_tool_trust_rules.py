"""Taint tracking: tool_trust_rules (org-scoped, row-level security).

Revision ID: b9w0x1y2z3a4
Revises: a8v9w0x1y2z3
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b9w0x1y2z3a4"
down_revision: Union[str, None] = "a8v9w0x1y2z3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORG_MATCH = "org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "tool_trust_rules",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_pattern", sa.String(200), nullable=False),
        sa.Column("rule", sa.String(20), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "tool_pattern", "rule", name="uq_tool_trust_rules_rule"),
        sa.CheckConstraint("rule IN ('trusted_output', 'sink')", name="ck_tool_trust_rules_rule"),
    )
    op.create_index("ix_tool_trust_rules_org_id", "tool_trust_rules", ["org_id"])
    op.execute("ALTER TABLE tool_trust_rules ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tool_trust_rules FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY rls_org_isolation ON tool_trust_rules FOR ALL USING ({_ORG_MATCH}) WITH CHECK ({_ORG_MATCH})"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON tool_trust_rules TO app_user")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS rls_org_isolation ON tool_trust_rules")
    op.drop_table("tool_trust_rules")
