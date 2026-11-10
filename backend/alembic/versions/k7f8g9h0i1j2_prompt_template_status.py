"""Prompt template lifecycle (Phase 3, slice 6): draft, active, retired. The promotion gate promotes a draft to active.

Revision ID: k7f8g9h0i1j2
Revises: j6e7f8g9h0i1
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k7f8g9h0i1j2"
down_revision: Union[str, None] = "j6e7f8g9h0i1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("prompt_templates", sa.Column("status", sa.String(10), nullable=False, server_default="active"))
    # is_active has always meant "the live version"; carry that over so nothing changes for existing templates.
    op.execute("UPDATE prompt_templates SET status = CASE WHEN is_active THEN 'active' ELSE 'retired' END")
    op.create_check_constraint("ck_prompt_templates_status", "prompt_templates", "status IN ('draft', 'active', 'retired')")
    op.create_index("idx_prompt_templates_org_status", "prompt_templates", ["org_id", "status"])
    # What an eval run actually tested, when it tested a prompt template: a fingerprint of the template's content. The
    # promotion gate only counts a run whose fingerprint still matches the template, so editing a prompt after its run
    # means the run no longer vouches for it.
    op.add_column("eval_runs", sa.Column("prompt_fingerprint", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("eval_runs", "prompt_fingerprint")
    op.drop_index("idx_prompt_templates_org_status", table_name="prompt_templates")
    op.drop_constraint("ck_prompt_templates_status", "prompt_templates", type_="check")
    op.drop_column("prompt_templates", "status")
