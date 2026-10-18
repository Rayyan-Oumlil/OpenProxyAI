"""Add mcp_servers for the MCP gateway (org-scoped, row-level security).

Revision ID: u2p3q4r5s6t7
Revises: t1o2p3q4r5s6
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "u2p3q4r5s6t7"
down_revision: Union[str, None] = "t1o2p3q4r5s6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORG_MATCH = "org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "mcp_servers",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("auth_header_encrypted", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "name", name="uq_mcp_servers_org_name"),
        sa.CheckConstraint("name ~ '^[a-z0-9-]{1,40}$'", name="ck_mcp_servers_name"),
    )
    op.create_index("ix_mcp_servers_org_id", "mcp_servers", ["org_id"])

    op.execute("ALTER TABLE mcp_servers ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE mcp_servers FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY rls_org_isolation ON mcp_servers FOR ALL USING ({_ORG_MATCH}) WITH CHECK ({_ORG_MATCH})"
    )
    # Default privileges from t1o2p3q4r5s6 cover new tables; explicit for clarity.
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON mcp_servers TO app_user")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS rls_org_isolation ON mcp_servers")
    op.drop_index("ix_mcp_servers_org_id", table_name="mcp_servers")
    op.drop_table("mcp_servers")
