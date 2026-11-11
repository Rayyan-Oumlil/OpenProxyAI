"""Context packages: an append-only record of what each conversation turn sent to the model (Phase 4, slice 3).

Revision ID: m9h0i1j2k3l4
Revises: l8g9h0i1j2k3
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "m9h0i1j2k3l4"
down_revision: Union[str, None] = "l8g9h0i1j2k3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORG_MATCH = "org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "conversation_context_packages",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assistant_turn_id", sa.Uuid(), sa.ForeignKey("conversation_turns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("data_class", sa.String(20), nullable=False),
        sa.Column("routing_mode", sa.String(10), nullable=False),
        sa.Column("included_turn_ids", postgresql.JSONB(), nullable=False),
        sa.Column("withheld", postgresql.JSONB(), nullable=False),
        sa.Column("estimated_tokens", sa.Integer(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("outcome IN ('ok', 'error')", name="ck_context_packages_outcome"),
    )
    op.create_index("ix_context_packages_conversation", "conversation_context_packages", ["conversation_id", "created_at"])
    table = "conversation_context_packages"
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY rls_org_isolation ON {table} FOR ALL USING ({_ORG_MATCH}) WITH CHECK ({_ORG_MATCH})")
    # Append-only: the application can record and read, never rewrite or remove (rows go with their conversation).
    # Default privileges may already have given the role more, so take it away explicitly.
    op.execute(f"REVOKE ALL ON {table} FROM app_user")
    op.execute(f"GRANT SELECT, INSERT ON {table} TO app_user")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS rls_org_isolation ON conversation_context_packages")
    op.drop_table("conversation_context_packages")
