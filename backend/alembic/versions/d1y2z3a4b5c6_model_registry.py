"""Model registry (org-scoped, row-level security).

Revision ID: d1y2z3a4b5c6
Revises: c0x1y2z3a4b5
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1y2z3a4b5c6"
down_revision: Union[str, None] = "c0x1y2z3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORG_MATCH = "org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "model_registry",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_id", sa.String(200), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_key_id", sa.Uuid(), sa.ForeignKey("llm_provider_keys.id", ondelete="SET NULL"), nullable=True),
        sa.Column("max_data_class", sa.String(20), nullable=False, server_default="internal"),
        sa.Column("regions", sa.JSON(), nullable=False),
        sa.Column("risk_rating", sa.String(10), nullable=False, server_default="medium"),
        sa.Column("retention_days", sa.Integer(), nullable=True),
        sa.Column("trains_on_data", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("capabilities", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("cost_tier", sa.String(10), nullable=True),
        sa.Column("owner", sa.String(200), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "model_id", name="uq_model_registry_org_model"),
        sa.CheckConstraint("max_data_class IN ('public', 'internal', 'confidential', 'secret')", name="ck_model_registry_data_class"),
        sa.CheckConstraint("risk_rating IN ('low', 'medium', 'high')", name="ck_model_registry_risk"),
        sa.CheckConstraint("cost_tier IS NULL OR cost_tier IN ('low', 'medium', 'high')", name="ck_model_registry_cost_tier"),
        sa.CheckConstraint("retention_days IS NULL OR retention_days >= 0", name="ck_model_registry_retention"),
    )
    op.create_index("ix_model_registry_org_id", "model_registry", ["org_id"])
    op.create_index("ix_model_registry_provider_key_id", "model_registry", ["provider_key_id"])
    op.execute("ALTER TABLE model_registry ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE model_registry FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY rls_org_isolation ON model_registry FOR ALL USING ({_ORG_MATCH}) WITH CHECK ({_ORG_MATCH})")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON model_registry TO app_user")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS rls_org_isolation ON model_registry")
    op.drop_table("model_registry")
