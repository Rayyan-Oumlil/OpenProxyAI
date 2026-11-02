"""Enforce row-level security on request_scores and scope its unique key to the org.

Revision ID: v3q4r5s6t7u8
Revises: u2p3q4r5s6t7
"""

from typing import Sequence, Union

from alembic import op

revision: str = "v3q4r5s6t7u8"
down_revision: Union[str, None] = "u2p3q4r5s6t7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORG_MATCH = "org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.execute("ALTER TABLE request_scores ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE request_scores FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY rls_org_isolation ON request_scores FOR ALL USING ({_ORG_MATCH}) WITH CHECK ({_ORG_MATCH})"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON request_scores TO app_user")

    # request_id is a gateway-generated UUID, but the global key let org B overwrite org A's score
    # by reusing a request_id. Scope uniqueness to the org.
    op.drop_constraint("uq_request_scores_request_name", "request_scores", type_="unique")
    op.create_unique_constraint(
        "uq_request_scores_org_request_name",
        "request_scores",
        ["org_id", "request_id", "score_name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_request_scores_org_request_name", "request_scores", type_="unique")
    op.create_unique_constraint(
        "uq_request_scores_request_name",
        "request_scores",
        ["request_id", "score_name"],
    )
    op.execute("DROP POLICY IF EXISTS rls_org_isolation ON request_scores")
    op.execute("ALTER TABLE request_scores NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE request_scores DISABLE ROW LEVEL SECURITY")
