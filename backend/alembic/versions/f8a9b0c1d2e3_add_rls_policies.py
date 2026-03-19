"""add RLS policies for multi-tenant isolation

Revision ID: f8a9b0c1d2e3
Revises: e6f7a34b9d0c
Create Date: 2026-03-19

Row-Level Security (RLS) enforces org_id isolation on tenant-scoped tables.
Policies use current_setting('app.current_org_id')::uuid. The application
must SET LOCAL app.current_org_id at the start of each request.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, None] = "e6f7a34b9d0c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RLS_TABLES = [
    "request_logs",
    "api_keys",
    "llm_provider_keys",
    "webhook_deliveries",
    "semantic_cache_entries",
    "prompt_templates",
]


def upgrade() -> None:
    # Create app_user role for application connections (superuser bypasses RLS)
    op.execute("DO $$ BEGIN CREATE ROLE app_user; EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute("""
        DO $$
        DECLARE db TEXT;
        BEGIN
            SELECT current_database() INTO db;
            EXECUTE format('GRANT CONNECT ON DATABASE %I TO app_user', db);
        END $$;
    """)
    op.execute("GRANT USAGE ON SCHEMA public TO app_user")
    for table in RLS_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user")

    # SECURITY DEFINER function for api_keys lookup by hash (needed before org_id is set)
    op.execute("""
        CREATE OR REPLACE FUNCTION public.get_api_key_by_hash(p_key_hash TEXT)
        RETURNS TABLE(
            id UUID,
            org_id UUID,
            user_id UUID,
            key_hash VARCHAR(255),
            key_prefix VARCHAR(20),
            name VARCHAR(100),
            permissions JSONB,
            is_active BOOLEAN,
            last_used_at TIMESTAMP,
            expires_at TIMESTAMP,
            created_at TIMESTAMP
        )
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public
        AS $$
            SELECT id, org_id, user_id, key_hash, key_prefix, name, permissions,
                   is_active, last_used_at, expires_at, created_at
            FROM api_keys
            WHERE api_keys.key_hash = p_key_hash;
        $$;
    """)
    op.execute("GRANT EXECUTE ON FUNCTION public.get_api_key_by_hash(TEXT) TO app_user")
    op.execute("""
        DO $$
        BEGIN
            EXECUTE format('GRANT app_user TO %I', current_user);
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Drop conflicting permissive policies on request_logs if present
    # (from f1a9c3e7d5b2; USING(true) would allow cross-org access)
    op.execute("DROP POLICY IF EXISTS request_logs_select ON request_logs")
    op.execute("DROP POLICY IF EXISTS request_logs_insert ON request_logs")

    # Enable RLS and create policies for each table
    policy_sql = (
        "org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid"
    )
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY rls_org_isolation ON {table}
            FOR ALL
            USING ({policy_sql})
            WITH CHECK ({policy_sql});
        """)


def downgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS rls_org_isolation ON {table}")
        if table != "request_logs":
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP FUNCTION IF EXISTS public.get_api_key_by_hash(TEXT)")

    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM app_user")
    op.execute("REVOKE USAGE ON SCHEMA public FROM app_user")
    op.execute("""
        DO $$
        DECLARE db TEXT;
        BEGIN
            SELECT current_database() INTO db;
            EXECUTE format('REVOKE CONNECT ON DATABASE %I FROM app_user', db);
        END $$;
    """)

    op.execute("""
        CREATE POLICY request_logs_insert ON request_logs
            FOR INSERT WITH CHECK (true)
    """)
    op.execute("""
        CREATE POLICY request_logs_select ON request_logs
            FOR SELECT USING (true)
    """)
