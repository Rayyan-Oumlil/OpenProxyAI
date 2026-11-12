"""Provider keys can be read from AWS Secrets Manager (secret_source 'aws').

The name of the secret goes in vault_path and the JSON field in vault_field: the columns hold "a reference to an external secret".

Revision ID: r4m5n6o7p8q9
Revises: q3l4m5n6o7p8
"""

from typing import Sequence, Union

from alembic import op

revision: str = "r4m5n6o7p8q9"
down_revision: Union[str, None] = "q3l4m5n6o7p8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_llm_provider_keys_secret_source", "llm_provider_keys", type_="check")
    op.create_check_constraint(
        "ck_llm_provider_keys_secret_source",
        "llm_provider_keys",
        "(secret_source = 'local' AND api_key_encrypted IS NOT NULL AND vault_path IS NULL)"
        " OR (secret_source IN ('vault', 'aws') AND api_key_encrypted IS NULL AND vault_path IS NOT NULL)",
    )


def downgrade() -> None:
    op.execute("DELETE FROM llm_provider_keys WHERE secret_source = 'aws'")
    op.drop_constraint("ck_llm_provider_keys_secret_source", "llm_provider_keys", type_="check")
    op.create_check_constraint(
        "ck_llm_provider_keys_secret_source",
        "llm_provider_keys",
        "(secret_source = 'local' AND api_key_encrypted IS NOT NULL AND vault_path IS NULL)"
        " OR (secret_source = 'vault' AND api_key_encrypted IS NULL AND vault_path IS NOT NULL)",
    )
