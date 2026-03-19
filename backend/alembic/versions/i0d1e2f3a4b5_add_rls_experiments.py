"""add RLS for experiments and experiment_variants

Revision ID: i0d1e2f3a4b5
Revises: h9c0d1e2f3a4
Create Date: 2026-03-19

"""
from typing import Sequence, Union

from alembic import op


revision: str = "i0d1e2f3a4b5"
down_revision: Union[str, None] = "h9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON experiments TO app_user")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON experiment_variants TO app_user")

    op.execute("ALTER TABLE experiments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE experiments FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY rls_org_isolation ON experiments
        FOR ALL
        USING (org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)
        WITH CHECK (org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid);
    """)

    op.execute("ALTER TABLE experiment_variants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE experiment_variants FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY rls_experiment_org_isolation ON experiment_variants
        FOR ALL
        USING (
            experiment_id IN (
                SELECT id FROM experiments
                WHERE org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid
            )
        )
        WITH CHECK (
            experiment_id IN (
                SELECT id FROM experiments
                WHERE org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid
            )
        );
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS rls_experiment_org_isolation ON experiment_variants")
    op.execute("ALTER TABLE experiment_variants DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS rls_org_isolation ON experiments")
    op.execute("ALTER TABLE experiments DISABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON experiments FROM app_user")
    op.execute("REVOKE ALL ON experiment_variants FROM app_user")
