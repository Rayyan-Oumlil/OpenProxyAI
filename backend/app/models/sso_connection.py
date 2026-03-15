"""SSO connection model — one generic OIDC connector per org."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SSOConnection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sso_connections"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    provider_name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # "auth0", "okta" etc. (display only)
    issuer_url: Mapped[str] = mapped_column(String(500), nullable=False)
    client_id: Mapped[str] = mapped_column(String(255), nullable=False)
    client_secret_encrypted: Mapped[str] = mapped_column(String, nullable=False)
    domain_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default="true", nullable=False
    )

    def __repr__(self) -> str:
        return f"<SSOConnection provider={self.provider_name!r} org={self.org_id}>"
