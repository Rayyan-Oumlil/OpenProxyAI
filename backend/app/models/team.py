"""Team model — departmental cost attribution within an organization."""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, Numeric, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.api_key import ApiKey
    from app.models.organization import Organization
    from app.models.user import User


# Association table for many-to-many: users <-> teams
team_members = Table(
    "team_members",
    Base.metadata,
    Column("team_id", ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)


class Team(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "teams"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    budget_monthly_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="teams")
    members: Mapped[list["User"]] = relationship(
        "User",
        secondary=team_members,
        back_populates="teams",
    )
    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="team")

    def __repr__(self) -> str:
        return f"<Team {self.name!r}>"
