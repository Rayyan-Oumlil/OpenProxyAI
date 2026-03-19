"""StripeEvent — idempotency log for processed Stripe webhook events."""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base, UUIDPrimaryKeyMixin


class StripeEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stripe_events"

    event_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<StripeEvent {self.event_id!r}>"
