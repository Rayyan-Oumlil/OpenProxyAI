"""add_gin_index_request_metadata

Revision ID: c4f9a12e8b7d
Revises: b3e8d87fd2f1
Create Date: 2026-03-13 08:00:00.000000

Adds a GIN index on request_logs.request_metadata using jsonb_path_ops so that
policy-field queries (e.g. `request_metadata->'policy'->>'action'`) use an index
scan instead of a sequential scan at scale.

CONCURRENTLY is used so the migration does not lock the table for writes.
This requires running outside a transaction block (autocommit_block).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4f9a12e8b7d"
down_revision: Union[str, None] = "b3e8d87fd2f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "idx_request_logs_policy_gin"


def upgrade() -> None:
	# CONCURRENTLY cannot run inside a transaction.
	with op.get_context().autocommit_block():
		op.execute(
			sa.text(
				f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX_NAME} "
				"ON request_logs USING gin(request_metadata jsonb_path_ops)"
			)
		)


def downgrade() -> None:
	with op.get_context().autocommit_block():
		op.execute(sa.text(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}"))
