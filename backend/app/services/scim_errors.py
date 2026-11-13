"""SCIM error type and response body (RFC 7644 section 3.12)."""

from __future__ import annotations

ERROR_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:Error"
SCIM_MEDIA_TYPE = "application/scim+json"


class ScimError(Exception):
    """Raised anywhere under /scim/v2; turned into a SCIM error body by the app's exception handler."""

    def __init__(self, status: int, detail: str, scim_type: str | None = None, headers: dict[str, str] | None = None) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.scim_type = scim_type
        self.headers = headers or {}

    def body(self) -> dict:
        body: dict = {"schemas": [ERROR_SCHEMA], "status": str(self.status), "detail": self.detail}
        if self.scim_type:
            body["scimType"] = self.scim_type
        return body
