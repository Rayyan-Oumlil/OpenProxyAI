"""Experiment model — A/B testing with traffic splitting."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class Experiment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "experiments"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_model: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="experiments")
    variants: Mapped[list["ExperimentVariant"]] = relationship(
        back_populates="experiment",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Experiment {self.name!r}>"


class ExperimentVariant(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "experiment_variants"

    experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    traffic_weight: Mapped[int] = mapped_column(Integer, nullable=False, server_default="50")

    # Relationships
    experiment: Mapped["Experiment"] = relationship(back_populates="variants")

    def __repr__(self) -> str:
        return f"<ExperimentVariant {self.model!r}>"
