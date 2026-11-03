"""MCP virtual bundles: mcp_bundles, mcp_bundle_tools, api_key_mcp_bundles (org-scoped, RLS).

Revision ID: a8v9w0x1y2z3
Revises: z7u8v9w0x1y2
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a8v9w0x1y2z3"
down_revision: Union[str, None] = "z7u8v9w0x1y2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORG_MATCH = "org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid"
_TABLES = ("api_key_mcp_bundles", "mcp_bundle_tools", "mcp_bundles")


def _protect(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY rls_org_isolation ON {table} FOR ALL USING ({_ORG_MATCH}) WITH CHECK ({_ORG_MATCH})")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user")


def upgrade() -> None:
    op.create_table(
        "mcp_bundles",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(40), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "slug", name="uq_mcp_bundles_org_slug"),
        sa.CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND char_length(slug) <= 40", name="ck_mcp_bundles_slug"),
    )
    op.create_index("ix_mcp_bundles_org_id", "mcp_bundles", ["org_id"])
    _protect("mcp_bundles")

    op.create_table(
        "mcp_bundle_tools",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bundle_id", sa.Uuid(), sa.ForeignKey("mcp_bundles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_pattern", sa.String(200), nullable=False),
        sa.UniqueConstraint("bundle_id", "tool_pattern", name="uq_mcp_bundle_tools_pattern"),
    )
    op.create_index("ix_mcp_bundle_tools_org_id", "mcp_bundle_tools", ["org_id"])
    op.create_index("ix_mcp_bundle_tools_bundle_id", "mcp_bundle_tools", ["bundle_id"])
    _protect("mcp_bundle_tools")

    op.create_table(
        "api_key_mcp_bundles",
        sa.Column("api_key_id", sa.Uuid(), sa.ForeignKey("api_keys.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("bundle_id", sa.Uuid(), sa.ForeignKey("mcp_bundles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("org_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_api_key_mcp_bundles_org_id", "api_key_mcp_bundles", ["org_id"])
    _protect("api_key_mcp_bundles")


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP POLICY IF EXISTS rls_org_isolation ON {table}")
        op.drop_table(table)
