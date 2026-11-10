"""Experiment model — A/B testing with traffic splitting."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
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

    # Adaptive A/B (Phase 3, slice 5). static = the weights are whatever an admin set. adaptive = a job moves them toward the
    # better variant as feedback arrives and stops the test, naming a winner, when one is clearly best (never before
    # min_samples_per_variant observations of each). The winner is only recorded: traffic is never switched automatically.
    mode: Mapped[str] = mapped_column(String(10), nullable=False, server_default="static")
    metric: Mapped[str | None] = mapped_column(String(100), nullable=True)  # a score name whose values are in [0, 1]
    min_samples_per_variant: Mapped[int] = mapped_column(Integer, nullable=False, server_default="30")
    delta: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, server_default="0.0100")  # stop at 1 - delta confidence
    weight_floor: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")  # no variant below this percent
    winner_variant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("experiment_variants.id", ondelete="SET NULL"), nullable=True)
    stopped_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)  # winner | manual
    adaptive_error: Mapped[str | None] = mapped_column(Text, nullable=True)  # why the job could not update this test
    adaptive_updated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="experiments")
    variants: Mapped[list["ExperimentVariant"]] = relationship(
        back_populates="experiment",
        cascade="all, delete-orphan",
        foreign_keys="ExperimentVariant.experiment_id",
        order_by="ExperimentVariant.id",  # a stable order: without one the API listed variants in whatever order Postgres returned
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
    experiment: Mapped["Experiment"] = relationship(back_populates="variants", foreign_keys=[experiment_id])

    def __repr__(self) -> str:
        return f"<ExperimentVariant {self.model!r}>"
