"""MCP tool pinning: mcp_tools, mcp_tool_versions (org-scoped, RLS) and mcp_servers.pin_mode.

Revision ID: x5s6t7u8v9w0
Revises: w4r5s6t7u8v9
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "x5s6t7u8v9w0"
down_revision: Union[str, None] = "w4r5s6t7u8v9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORG_MATCH = "org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY rls_org_isolation ON {table} FOR ALL USING ({_ORG_MATCH}) WITH CHECK ({_ORG_MATCH})")


def upgrade() -> None:
    op.add_column("mcp_servers", sa.Column("pin_mode", sa.String(10), nullable=False, server_default="warn"))
    op.create_check_constraint("ck_mcp_servers_pin_mode", "mcp_servers", "pin_mode IN ('off', 'warn', 'enforce')")

    op.create_table(
        "mcp_tools",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("server_id", sa.Uuid(), sa.ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("definition", JSONB(), nullable=False),
        sa.Column("current_hash", sa.String(64), nullable=False),
        sa.Column("approved_hash", sa.String(64), nullable=True),
        sa.Column("approved_snapshot", JSONB(), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("approved_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("server_id", "name", name="uq_mcp_tools_server_name"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'drifted', 'blocked')", name="ck_mcp_tools_status"),
    )
    op.create_index("ix_mcp_tools_org_id", "mcp_tools", ["org_id"])
    op.create_index("ix_mcp_tools_server_id", "mcp_tools", ["server_id"])
    _enable_rls("mcp_tools")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON mcp_tools TO app_user")

    op.create_table(
        "mcp_tool_versions",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_id", sa.Uuid(), sa.ForeignKey("mcp_tools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.Column("definition", JSONB(), nullable=False),
        sa.Column("seen_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tool_id", "hash", name="uq_mcp_tool_versions_tool_hash"),
    )
    op.create_index("ix_mcp_tool_versions_org_id", "mcp_tool_versions", ["org_id"])
    op.create_index("ix_mcp_tool_versions_tool_id", "mcp_tool_versions", ["tool_id"])
    _enable_rls("mcp_tool_versions")
    # History is append-only for the request role; cascades from mcp_tools/mcp_servers run as the owner.
    # Default privileges (t1o2p3q4r5s6) already granted everything, so revoke explicitly.
    op.execute("GRANT SELECT, INSERT ON mcp_tool_versions TO app_user")
    op.execute("REVOKE UPDATE, DELETE ON mcp_tool_versions FROM app_user")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS rls_org_isolation ON mcp_tool_versions")
    op.drop_table("mcp_tool_versions")
    op.execute("DROP POLICY IF EXISTS rls_org_isolation ON mcp_tools")
    op.drop_table("mcp_tools")
    op.drop_constraint("ck_mcp_servers_pin_mode", "mcp_servers", type_="check")
    op.drop_column("mcp_servers", "pin_mode")
