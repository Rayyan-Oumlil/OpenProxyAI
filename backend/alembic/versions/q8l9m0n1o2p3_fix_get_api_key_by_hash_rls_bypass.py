"""Replace get_api_key_by_hash with api_key_lookup table (no RLS bypass)

Revision ID: q8l9m0n1o2p3
Revises: p7k8l9m0n1o2
Create Date: 2026-03-22

Instead of bypassing RLS via a SECURITY DEFINER function, use a dedicated
api_key_lookup table without RLS. Validation: lookup key_hash -> org_id, set
session, then load ApiKey from api_keys (RLS applies). Keeps tenant isolation.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "q8l9m0n1o2p3"
down_revision: Union[str, None] = "o6j7k8l9m0n1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Grant app_user to openproxyai so app can validate keys and access RLS tables
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'openproxyai') THEN
                EXECUTE 'GRANT app_user TO openproxyai';
            END IF;
        END $$;
    """)

    # Dedicated lookup table — no RLS; only key_hash, org_id, api_key_id for validation
    op.create_table(
        "api_key_lookup",
        sa.Column("key_hash", sa.String(255), primary_key=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("api_key_id", sa.Uuid(), sa.ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=False),
    )
    op.execute("GRANT SELECT, INSERT, DELETE ON api_key_lookup TO app_user")

    # Populate from existing api_keys (iterate orgs to satisfy RLS)
    op.execute("""
        DO $$
        DECLARE r RECORD;
        BEGIN
            FOR r IN SELECT id FROM organizations
            LOOP
                PERFORM set_config('app.current_org_id', r.id::text, true);
                INSERT INTO api_key_lookup (key_hash, org_id, api_key_id)
                SELECT key_hash, org_id, id FROM api_keys
                ON CONFLICT (key_hash) DO NOTHING;
            END LOOP;
        END $$;
    """)

    op.execute("DROP FUNCTION IF EXISTS public.get_api_key_by_hash(TEXT)")
    op.execute("DROP ROLE IF EXISTS app_key_lookup")


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION public.get_api_key_by_hash(p_key_hash TEXT)
        RETURNS TABLE(
            id UUID, org_id UUID, user_id UUID, key_hash VARCHAR(255),
            key_prefix VARCHAR(20), name VARCHAR(100), permissions JSONB,
            is_active BOOLEAN, last_used_at TIMESTAMP, expires_at TIMESTAMP, created_at TIMESTAMP
        )
        LANGUAGE sql SECURITY DEFINER SET search_path = public
        AS $$ SELECT id, org_id, user_id, key_hash, key_prefix, name, permissions,
           is_active, last_used_at, expires_at, created_at FROM api_keys WHERE api_keys.key_hash = p_key_hash; $$;
    """)
    op.execute("GRANT EXECUTE ON FUNCTION public.get_api_key_by_hash(TEXT) TO app_user")
    op.drop_table("api_key_lookup")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'openproxyai') THEN
                EXECUTE 'REVOKE app_user FROM openproxyai';
            END IF;
        END $$;
    """)
