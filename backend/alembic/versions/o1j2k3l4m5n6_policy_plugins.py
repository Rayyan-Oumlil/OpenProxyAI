"""WebAssembly policy plugins (Phase 5, slice 5.11). Org-scoped by RLS.

Revision ID: o1j2k3l4m5n6
Revises: n0i1j2k3l4m5
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "o1j2k3l4m5n6"
down_revision: Union[str, None] = "n0i1j2k3l4m5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORG_MATCH = "org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "policy_plugins",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("module", sa.LargeBinary(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "name", name="uq_policy_plugins_org_name"),
        sa.CheckConstraint("size_bytes > 0 AND size_bytes <= 1048576", name="ck_policy_plugins_size"),
    )
    op.execute("ALTER TABLE policy_plugins ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE policy_plugins FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY rls_org_isolation ON policy_plugins FOR ALL USING ({_ORG_MATCH}) WITH CHECK ({_ORG_MATCH})")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON policy_plugins TO app_user")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS rls_org_isolation ON policy_plugins")
    op.drop_table("policy_plugins")
