"""audit_log_immutability

Revision ID: f1a9c3e7d5b2
Revises: e5f8a23b4c1d
Create Date: 2026-03-15 14:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f1a9c3e7d5b2'
down_revision: Union[str, None] = 'e5f8a23b4c1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add archived_at column for soft archival
    op.add_column(
        'request_logs',
        sa.Column('archived_at', sa.DateTime(), nullable=True),
    )
    op.create_index(
        'idx_request_logs_archived_at',
        'request_logs',
        ['archived_at'],
        unique=False,
    )

    # Enable Row-Level Security on request_logs
    op.execute('ALTER TABLE request_logs ENABLE ROW LEVEL SECURITY')

    # Create app_user role if it doesn't exist (idempotent)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                CREATE ROLE app_user;
            END IF;
        END
        $$;
    """)

    # Allow INSERT (audit logger)
    op.execute("""
        CREATE POLICY request_logs_insert ON request_logs
            FOR INSERT WITH CHECK (true)
    """)

    # Allow SELECT (analytics, log viewer)
    op.execute("""
        CREATE POLICY request_logs_select ON request_logs
            FOR SELECT USING (true)
    """)

    # Explicitly NO UPDATE or DELETE policy = blocked by RLS for app_user
    # The superuser / migration role can still update for maintenance


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS request_logs_select ON request_logs')
    op.execute('DROP POLICY IF EXISTS request_logs_insert ON request_logs')
    op.execute('ALTER TABLE request_logs DISABLE ROW LEVEL SECURITY')
    op.drop_index('idx_request_logs_archived_at', table_name='request_logs')
    op.drop_column('request_logs', 'archived_at')
