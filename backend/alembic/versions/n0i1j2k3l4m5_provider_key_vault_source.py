"""Provider keys can be read from HashiCorp Vault instead of being stored encrypted (Phase 5, slice 5.10).

Revision ID: n0i1j2k3l4m5
Revises: m9h0i1j2k3l4
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n0i1j2k3l4m5"
down_revision: Union[str, None] = "m9h0i1j2k3l4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("llm_provider_keys", sa.Column("secret_source", sa.String(10), nullable=False, server_default="local"))
    op.add_column("llm_provider_keys", sa.Column("vault_path", sa.String(500), nullable=True))
    op.add_column("llm_provider_keys", sa.Column("vault_field", sa.String(100), nullable=True))
    # A Vault-backed key holds no secret of its own.
    op.alter_column("llm_provider_keys", "api_key_encrypted", existing_type=sa.Text(), nullable=True)
    op.create_check_constraint(
        "ck_llm_provider_keys_secret_source",
        "llm_provider_keys",
        "(secret_source = 'local' AND api_key_encrypted IS NOT NULL AND vault_path IS NULL)"
        " OR (secret_source = 'vault' AND api_key_encrypted IS NULL AND vault_path IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_llm_provider_keys_secret_source", "llm_provider_keys", type_="check")
    # Vault-backed keys have nothing to put back; they cannot survive a downgrade.
    op.execute("DELETE FROM llm_provider_keys WHERE secret_source = 'vault'")
    op.alter_column("llm_provider_keys", "api_key_encrypted", existing_type=sa.Text(), nullable=False)
    op.drop_column("llm_provider_keys", "vault_field")
    op.drop_column("llm_provider_keys", "vault_path")
    op.drop_column("llm_provider_keys", "secret_source")
