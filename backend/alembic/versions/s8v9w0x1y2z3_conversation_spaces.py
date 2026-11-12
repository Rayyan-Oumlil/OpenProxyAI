"""Project spaces: named folders a conversation can belong to. Org-scoped by RLS.

A space never widens who can read a conversation; it only groups what the caller can already see.

Revision ID: s8v9w0x1y2z3
Revises: r4m5n6o7p8q9
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "s8v9w0x1y2z3"
down_revision: Union[str, None] = "r4m5n6o7p8q9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORG_MATCH = "org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "spaces",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        # Deleting the team turns the space personal (a CHECK demanding a team would make deleting a team fail).
        sa.Column("team_id", sa.Uuid(), sa.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.execute("CREATE UNIQUE INDEX uq_spaces_owner_name ON spaces (owner_id, lower(name))")
    op.create_index("ix_spaces_org_team", "spaces", ["org_id", "team_id"])
    op.execute("ALTER TABLE spaces ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE spaces FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY rls_org_isolation ON spaces FOR ALL USING ({_ORG_MATCH}) WITH CHECK ({_ORG_MATCH})")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON spaces TO app_user")

    op.add_column("conversations", sa.Column("space_id", sa.Uuid(), sa.ForeignKey("spaces.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_conversations_space", "conversations", ["space_id"])


def downgrade() -> None:
    op.drop_index("ix_conversations_space", table_name="conversations")
    op.drop_column("conversations", "space_id")
    op.execute("DROP POLICY IF EXISTS rls_org_isolation ON spaces")
    op.drop_table("spaces")
