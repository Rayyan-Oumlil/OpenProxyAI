"""fix missing gen_random_uuid() defaults on teams, experiments, request_scores

Revision ID: s0n1o2p3q4r5
Revises: r9m0n1o2p3q4
Create Date: 2026-03-23

"""
from typing import Sequence, Union
from alembic import op

revision: str = "s0n1o2p3q4r5"
down_revision: Union[str, None] = "r9m0n1o2p3q4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE teams ALTER COLUMN id SET DEFAULT gen_random_uuid()")
    op.execute("ALTER TABLE experiments ALTER COLUMN id SET DEFAULT gen_random_uuid()")
    op.execute("ALTER TABLE experiment_variants ALTER COLUMN id SET DEFAULT gen_random_uuid()")
    op.execute("ALTER TABLE request_scores ALTER COLUMN id SET DEFAULT gen_random_uuid()")


def downgrade() -> None:
    op.execute("ALTER TABLE teams ALTER COLUMN id DROP DEFAULT")
    op.execute("ALTER TABLE experiments ALTER COLUMN id DROP DEFAULT")
    op.execute("ALTER TABLE experiment_variants ALTER COLUMN id DROP DEFAULT")
    op.execute("ALTER TABLE request_scores ALTER COLUMN id DROP DEFAULT")
