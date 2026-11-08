"""Provider keys can point at a custom endpoint and declare the data class they may receive.

Revision ID: c0x1y2z3a4b5
Revises: b9w0x1y2z3a4
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c0x1y2z3a4b5"
down_revision: Union[str, None] = "b9w0x1y2z3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("llm_provider_keys", sa.Column("api_base", sa.String(500), nullable=True))
    op.add_column(
        "llm_provider_keys",
        sa.Column("max_data_class", sa.String(20), nullable=False, server_default="internal"),
    )
    op.add_column(
        "llm_provider_keys",
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_check_constraint(
        "ck_llm_provider_keys_max_data_class",
        "llm_provider_keys",
        "max_data_class IN ('public', 'internal', 'confidential', 'secret')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_llm_provider_keys_max_data_class", "llm_provider_keys", type_="check")
    op.drop_column("llm_provider_keys", "is_internal")
    op.drop_column("llm_provider_keys", "max_data_class")
    op.drop_column("llm_provider_keys", "api_base")
