"""add region to llm_provider_keys

Revision ID: f7a8b9c0d1e2
Revises: e6f7a34b9d0c
Create Date: 2026-03-19

"""
from alembic import op
import sqlalchemy as sa


revision = "f7a8b9c0d1e2"
down_revision = "e6f7a34b9d0c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "llm_provider_keys",
        sa.Column("region", sa.String(10), nullable=False, server_default="us"),
    )
    op.create_check_constraint(
        "ck_provider_keys_region_valid",
        "llm_provider_keys",
        "region IN ('us', 'eu', 'ap', 'global')",
    )
    op.create_index(
        "idx_provider_keys_org_region",
        "llm_provider_keys",
        ["org_id", "region", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("idx_provider_keys_org_region", table_name="llm_provider_keys")
    op.drop_constraint("ck_provider_keys_region_valid", "llm_provider_keys", type_="check")
    op.drop_column("llm_provider_keys", "region")
