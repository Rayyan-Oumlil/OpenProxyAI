"""add_mv_daily_spend_unique_index

Revision ID: b3e8d87fd2f1
Revises: 54c0ed90559e
Create Date: 2026-03-12 23:45:00.000000
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3e8d87fd2f1"
down_revision: Union[str, None] = "54c0ed90559e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEX_NAME = "idx_mv_daily_spend_unique"


def upgrade() -> None:
	op.execute(
		f"""
		CREATE UNIQUE INDEX IF NOT EXISTS {INDEX_NAME}
		ON mv_daily_spend (org_id, user_id, model, provider, day)
		"""
	)


def downgrade() -> None:
	op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
