"""SCIM provisioning: per-org bearer tokens (hashed) and an external id on users.

Revision ID: u6s7c8i9m0t1
Revises: r4m5n6o7p8q9

scim_tokens is org-scoped by row-level security (admin management). scim_token_lookup has no RLS and holds only
hash -> org, so a request can find its org before an org is set (the same pattern as api_key_lookup).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "u6s7c8i9m0t1"
down_revision: Union[str, None] = "r4m5n6o7p8q9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORG_MATCH = "org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "scim_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_prefix", sa.String(16), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_scim_tokens_org_id", "scim_tokens", ["org_id"])
    # At most one live token per org: rotating replaces it, never adds a second.
    op.create_index(
        "uq_scim_tokens_one_live_per_org", "scim_tokens", ["org_id"], unique=True, postgresql_where=sa.text("revoked_at IS NULL")
    )
    op.execute("ALTER TABLE scim_tokens ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE scim_tokens FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY rls_org_isolation ON scim_tokens FOR ALL USING ({_ORG_MATCH}) WITH CHECK ({_ORG_MATCH})")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON scim_tokens TO app_user")

    op.create_table(
        "scim_token_lookup",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("token_id", sa.Uuid(), sa.ForeignKey("scim_tokens.id", ondelete="CASCADE"), nullable=False),
    )
    op.execute("GRANT SELECT, INSERT, DELETE ON scim_token_lookup TO app_user")

    op.add_column("users", sa.Column("external_id", sa.String(255), nullable=True))
    # SCIM may only touch users it created itself; every existing user is false, so an identity provider cannot take one over.
    op.add_column("users", sa.Column("scim_managed", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.create_index(
        "uq_users_org_external_id", "users", ["org_id", "external_id"], unique=True, postgresql_where=sa.text("external_id IS NOT NULL")
    )


def downgrade() -> None:
    op.drop_index("uq_users_org_external_id", table_name="users")
    op.drop_column("users", "scim_managed")
    op.drop_column("users", "external_id")
    op.drop_table("scim_token_lookup")
    op.execute("DROP POLICY IF EXISTS rls_org_isolation ON scim_tokens")
    op.drop_table("scim_tokens")
