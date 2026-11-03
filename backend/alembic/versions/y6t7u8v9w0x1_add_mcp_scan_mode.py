"""MCP output/description injection scanning: mcp_servers.scan_mode (off | log | redact | block).

Default is 'log': existing servers start reporting findings without changing what agents receive.

Revision ID: y6t7u8v9w0x1
Revises: x5s6t7u8v9w0
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "y6t7u8v9w0x1"
down_revision: Union[str, None] = "x5s6t7u8v9w0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("mcp_servers", sa.Column("scan_mode", sa.String(10), nullable=False, server_default="log"))
    op.create_check_constraint("ck_mcp_servers_scan_mode", "mcp_servers", "scan_mode IN ('off', 'log', 'redact', 'block')")


def downgrade() -> None:
    op.drop_constraint("ck_mcp_servers_scan_mode", "mcp_servers", type_="check")
    op.drop_column("mcp_servers", "scan_mode")
