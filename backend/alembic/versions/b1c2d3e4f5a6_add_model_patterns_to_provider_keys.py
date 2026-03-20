"""add model_patterns to llm_provider_keys

Revision ID: b1c2d3e4f5a6
Revises: a3b4c5d6e7f8
Create Date: 2026-03-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'b1c2d3e4f5a6'
down_revision = 'a3b4c5d6e7f8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'llm_provider_keys',
        sa.Column('model_patterns', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='[]')
    )


def downgrade() -> None:
    op.drop_column('llm_provider_keys', 'model_patterns')
