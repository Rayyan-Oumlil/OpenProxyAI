"""merge RLS branch into main migration chain

Revision ID: k2f3a4b5c6d7
Revises: j1e2f3a4b5c6, f8a9b0c1d2e3
Create Date: 2026-03-19

Merges the f8a9b0c1d2e3 (add_rls_policies) branch, which diverged from
e6f7a34b9d0c, back into the main chain ending at j1e2f3a4b5c6.
"""
from typing import Sequence, Union

from alembic import op  # noqa: F401


revision: str = "k2f3a4b5c6d7"
down_revision: Union[tuple[str, str], None] = ("j1e2f3a4b5c6", "f8a9b0c1d2e3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
