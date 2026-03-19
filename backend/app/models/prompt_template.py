"""Prompt template model — saved prompts with variable placeholders for the Playground."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class PromptTemplate(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "prompt_templates"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_template: Mapped[str] = mapped_column(Text, nullable=False)
    variables_schema: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="prompt_templates")
    creator: Mapped["User | None"] = relationship()

    def __repr__(self) -> str:
        return f"<PromptTemplate {self.name!r} v{self.version}>"
