"""Admin audit log response schemas."""

from pydantic import BaseModel


class AdminAuditLogResponse(BaseModel):
    id: str
    actor_email: str
    action: str
    resource_type: str
    resource_id: str | None
    before: dict | None
    after: dict | None
    ip_address: str | None
    created_at: str

    model_config = {"from_attributes": True}
