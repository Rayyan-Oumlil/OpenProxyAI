"""experiment constraints and request_logs experiment index

Revision ID: j1e2f3a4b5c6
Revises: i0d1e2f3a4b5
Create Date: 2026-03-19

Adds:
- Unique partial index: one active experiment per (org_id, target_model)
- CHECK constraint: experiment_variants.traffic_weight between 1 and 100
- Functional index on request_logs for experiment results queries
"""
from typing import Sequence, Union

from alembic import op


revision: str = "j1e2f3a4b5c6"
down_revision: Union[str, None] = "i0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # One active experiment per (org_id, target_model)
    op.execute("""
        CREATE UNIQUE INDEX idx_experiments_org_target_active_unique
        ON experiments (org_id, target_model)
        WHERE is_active = true
    """)

    # traffic_weight must be 1-100
    op.execute("""
        ALTER TABLE experiment_variants
        ADD CONSTRAINT chk_experiment_variants_traffic_weight
        CHECK (traffic_weight >= 1 AND traffic_weight <= 100)
    """)

    # Index for experiment results: request_metadata->'experiment'->>'experiment_id'
    op.execute("""
        CREATE INDEX idx_request_logs_experiment_id
        ON request_logs ((request_metadata->'experiment'->>'experiment_id'))
        WHERE request_metadata->'experiment'->>'experiment_id' IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_request_logs_experiment_id")
    op.execute("ALTER TABLE experiment_variants DROP CONSTRAINT IF EXISTS chk_experiment_variants_traffic_weight")
    op.execute("DROP INDEX IF EXISTS idx_experiments_org_target_active_unique")
