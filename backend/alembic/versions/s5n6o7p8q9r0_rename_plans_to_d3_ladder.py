"""Rename plans to the D3 ladder: free -> community, starter -> team, growth -> business.

Existing organizations keep their entitlements (the features move with the new keys); only the stored names change.
The column default moves to 'community' too, so a new organization starts on the free tier.

Revision ID: s5n6o7p8q9r0
Revises: r4m5n6o7p8q9
"""

from typing import Sequence, Union

from alembic import op

revision: str = "s5n6o7p8q9r0"
down_revision: Union[str, None] = "r4m5n6o7p8q9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RENAMES = (("free", "community"), ("starter", "team"), ("growth", "business"))


def _rename(pairs: Sequence[tuple[str, str]], default: str) -> None:
    for old, new in pairs:
        op.execute(f"UPDATE organizations SET plan = '{new}' WHERE plan = '{old}'")
    op.execute(f"ALTER TABLE organizations ALTER COLUMN plan SET DEFAULT '{default}'")


def upgrade() -> None:
    _rename(_RENAMES, "community")


def downgrade() -> None:
    _rename(tuple((new, old) for old, new in _RENAMES), "free")
