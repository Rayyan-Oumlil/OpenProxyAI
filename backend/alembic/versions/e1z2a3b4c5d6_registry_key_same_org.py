"""A registry entry can only link to a provider key of its own organization, enforced by the database.

Row-level security does not apply to foreign-key checks, so a plain foreign key would accept another org's key id
if the application check were ever bypassed. The composite key names the org.

Revision ID: e1z2a3b4c5d6
Revises: d1y2z3a4b5c6
"""

from typing import Sequence, Union

from alembic import op

revision: str = "e1z2a3b4c5d6"
down_revision: Union[str, None] = "d1y2z3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE llm_provider_keys ADD CONSTRAINT uq_llm_provider_keys_org_id_id UNIQUE (org_id, id)")
    op.execute("ALTER TABLE model_registry DROP CONSTRAINT model_registry_provider_key_id_fkey")
    # ON DELETE SET NULL (column) needs PostgreSQL 15+: deleting a key detaches the entry but never touches its org_id.
    op.execute(
        "ALTER TABLE model_registry ADD CONSTRAINT fk_model_registry_key_same_org "
        "FOREIGN KEY (org_id, provider_key_id) REFERENCES llm_provider_keys (org_id, id) ON DELETE SET NULL (provider_key_id)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE model_registry DROP CONSTRAINT fk_model_registry_key_same_org")
    op.execute(
        "ALTER TABLE model_registry ADD CONSTRAINT model_registry_provider_key_id_fkey "
        "FOREIGN KEY (provider_key_id) REFERENCES llm_provider_keys (id) ON DELETE SET NULL"
    )
    op.execute("ALTER TABLE llm_provider_keys DROP CONSTRAINT uq_llm_provider_keys_org_id_id")
