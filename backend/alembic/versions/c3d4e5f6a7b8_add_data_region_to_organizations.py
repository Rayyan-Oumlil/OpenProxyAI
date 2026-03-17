"""add data_region to organizations

Revision ID: c3d4e5f6a7b8
Revises: b1c2d3e4f5a6
Create Date: 2026-03-16

"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6a7b8'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'organizations',
        sa.Column('data_region', sa.String(50), nullable=True, server_default='us')
    )


def downgrade() -> None:
    op.drop_column('organizations', 'data_region')
