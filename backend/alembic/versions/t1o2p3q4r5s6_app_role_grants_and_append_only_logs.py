"""Grant app_user the privileges the app needs; make audit logs append-only again.

The application now runs every request-path connection as ``app_user`` (SET ROLE, see
app/database.py) so row-level security applies even when the login role is a superuser.
Until now app_user only had privileges on the RLS tables.

``f8a9b0c1d2e3`` replaced the insert/select-only policies on request_logs with a FOR ALL
policy, which let the app role UPDATE and DELETE its own org's logs. Policies cannot limit
columns, so immutability is enforced with privileges instead: no DELETE, and UPDATE only on
``archived_at`` (the archive job sets it).

Revision ID: t1o2p3q4r5s6
Revises: s0n1o2p3q4r5
"""

from typing import Sequence, Union

from alembic import op

revision: str = "t1o2p3q4r5s6"
down_revision: Union[str, None] = "s0n1o2p3q4r5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("GRANT USAGE ON SCHEMA public TO app_user")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user")
    op.execute("GRANT SELECT ON mv_daily_spend TO app_user")
    # Runs as the view owner (SECURITY DEFINER); explicit so it does not rely on PUBLIC defaults.
    op.execute("GRANT EXECUTE ON FUNCTION refresh_mv_daily_spend_definer() TO app_user")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user"
    )
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app_user")

    # The app must never rewrite its own migration history.
    op.execute("REVOKE ALL ON alembic_version FROM app_user")

    # Append-only audit trails.
    op.execute("REVOKE UPDATE, DELETE ON request_logs FROM app_user")
    op.execute("GRANT UPDATE (archived_at) ON request_logs TO app_user")
    op.execute("REVOKE UPDATE, DELETE ON admin_audit_logs FROM app_user")


def downgrade() -> None:
    op.execute("GRANT UPDATE, DELETE ON admin_audit_logs TO app_user")
    op.execute("REVOKE UPDATE (archived_at) ON request_logs FROM app_user")
    op.execute("GRANT UPDATE, DELETE ON request_logs TO app_user")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE USAGE, SELECT ON SEQUENCES FROM app_user")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM app_user"
    )
    op.execute("REVOKE EXECUTE ON FUNCTION refresh_mv_daily_spend_definer() FROM app_user")
    op.execute("REVOKE SELECT ON mv_daily_spend FROM app_user")
    op.execute("REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public FROM app_user")
    op.execute("REVOKE SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM app_user")
    # Restore the RLS-table grants f8a9b0c1d2e3 created.
    for table in (
        "request_logs", "api_keys", "llm_provider_keys", "webhook_deliveries",
        "semantic_cache_entries", "prompt_templates", "experiments", "experiment_variants",
    ):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user")
    op.execute("GRANT SELECT, INSERT, DELETE ON api_key_lookup TO app_user")
