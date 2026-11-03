"""MCP per-tool grants (org-scoped, row-level security).

Revision ID: z7u8v9w0x1y2
Revises: y6t7u8v9w0x1
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "z7u8v9w0x1y2"
down_revision: Union[str, None] = "y6t7u8v9w0x1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORG_MATCH = "org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "tool_grants",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_type", sa.String(10), nullable=False),
        sa.Column("subject_id", sa.String(64), nullable=False),
        sa.Column("tool_pattern", sa.String(200), nullable=False),
        sa.Column("effect", sa.String(5), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "subject_type", "subject_id", "tool_pattern", "effect", name="uq_tool_grants_rule"),
        sa.CheckConstraint("subject_type IN ('role', 'team', 'user', 'api_key')", name="ck_tool_grants_subject_type"),
        sa.CheckConstraint("effect IN ('allow', 'deny')", name="ck_tool_grants_effect"),
    )
    op.create_index("ix_tool_grants_org_id", "tool_grants", ["org_id"])
    op.execute("ALTER TABLE tool_grants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tool_grants FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY rls_org_isolation ON tool_grants FOR ALL USING ({_ORG_MATCH}) WITH CHECK ({_ORG_MATCH})")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON tool_grants TO app_user")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS rls_org_isolation ON tool_grants")
    op.drop_table("tool_grants")
