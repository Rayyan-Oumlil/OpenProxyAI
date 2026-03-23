"""Add SECURITY DEFINER function for mv_daily_spend refresh

Revision ID: r9m0n1o2p3q4
Revises: q8l9m0n1o2p3
Create Date: 2026-03-21

mv_daily_spend aggregates from request_logs. When the app (openproxyai) runs
REFRESH, RLS on request_logs filters to 0 rows (no app.current_org_id), so the
MV stays empty. This function runs as the definer (postgres) and bypasses RLS,
allowing the app to refresh the MV with a single SELECT.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "r9m0n1o2p3q4"
down_revision: Union[str, None] = "q8l9m0n1o2p3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION refresh_mv_daily_spend_definer()
        RETURNS void
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public
        AS $$
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_spend;
        $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'openproxyai') THEN
                GRANT EXECUTE ON FUNCTION refresh_mv_daily_spend_definer() TO openproxyai;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS refresh_mv_daily_spend_definer()")
