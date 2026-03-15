"""add_sso_to_users

Revision ID: e5f8a23b4c1d
Revises: d4e7f12a9c3b
Create Date: 2026-03-15 12:00:00.000000

Creates the sso_connections table and adds SSO fields to the users table.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e5f8a23b4c1d'
down_revision: Union[str, None] = 'd4e7f12a9c3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sso_connections',
        sa.Column('org_id', sa.Uuid(), nullable=False),
        sa.Column('provider_name', sa.String(length=100), nullable=False),
        sa.Column('issuer_url', sa.String(length=500), nullable=False),
        sa.Column('client_id', sa.String(length=255), nullable=False),
        sa.Column('client_secret_encrypted', sa.Text(), nullable=False),
        sa.Column('domain_hint', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.add_column('users', sa.Column('sso_sub', sa.String(length=500), nullable=True))
    op.add_column('users', sa.Column('sso_connection_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_users_sso_connection',
        'users', 'sso_connections',
        ['sso_connection_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_users_sso_connection', 'users', type_='foreignkey')
    op.drop_column('users', 'sso_connection_id')
    op.drop_column('users', 'sso_sub')
    op.drop_table('sso_connections')
