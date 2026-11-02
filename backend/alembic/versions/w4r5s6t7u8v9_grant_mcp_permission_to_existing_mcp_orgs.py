"""Grant proxy:mcp to existing API keys of organisations that already use the MCP gateway.

POST /v1/mcp now requires the proxy:mcp key permission (it was previously ignored). Without this
backfill, every key an org already uses for MCP would start returning 403 on deploy. Only orgs that
have configured at least one MCP server are touched; everyone else opts in explicitly.

Revision ID: w4r5s6t7u8v9
Revises: v3q4r5s6t7u8
"""

from typing import Sequence, Union

from alembic import op

revision: str = "w4r5s6t7u8v9"
down_revision: Union[str, None] = "v3q4r5s6t7u8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # api_keys and mcp_servers are RLS-protected: iterate orgs and set the session org, as q8l9m0n1o2p3 does.
    # The explicit org_id predicates matter too: a superuser migration role bypasses RLS entirely.
    op.execute("""
        DO $$
        DECLARE r RECORD;
        BEGIN
            FOR r IN SELECT id FROM organizations
            LOOP
                PERFORM set_config('app.current_org_id', r.id::text, true);
                UPDATE api_keys
                SET permissions = permissions || '["proxy:mcp"]'::jsonb
                WHERE org_id = r.id
                  AND EXISTS (SELECT 1 FROM mcp_servers WHERE mcp_servers.org_id = r.id)
                  AND NOT (permissions @> '["proxy:mcp"]'::jsonb);
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        DECLARE r RECORD;
        BEGIN
            FOR r IN SELECT id FROM organizations
            LOOP
                PERFORM set_config('app.current_org_id', r.id::text, true);
                UPDATE api_keys SET permissions = permissions - 'proxy:mcp' WHERE org_id = r.id;
            END LOOP;
        END $$;
    """)
