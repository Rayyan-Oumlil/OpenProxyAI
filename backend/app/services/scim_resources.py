"""SCIM User resource: mapping to and from our users table, filters, and PATCH.

Mapping (our model is smaller than the SCIM core schema, on purpose):
- userName = email (lower-cased). ``emails`` is accepted but userName is the one source of truth.
- name / displayName = users.name (one string). ``name.givenName`` + ``name.familyName`` are joined on the way in.
- active = users.is_active. externalId = users.external_id.
- Roles are NOT mapped: a SCIM request that carries roles is refused, so provisioning can never grant admin.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import EmailStr, TypeAdapter, ValidationError

from app.models.user import User
from app.services.scim_errors import ScimError

USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
LIST_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:ListResponse"
PATCH_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:PatchOp"

MAX_PAGE = 200
DEFAULT_PAGE = 100
_NAME_MAX = 255
_EMAIL = TypeAdapter(EmailStr)
_FILTER = re.compile(r'^\s*(userName|externalId|id)\s+eq\s+"((?:[^"\\]|\\.)*)"\s*$', re.IGNORECASE)
_ROLE_KEYS = {"roles", "entitlements", "groups"}


def _stamp(value) -> str | None:
    return value.isoformat() + "Z" if value else None


def to_scim_user(user: User, base_url: str) -> dict[str, Any]:
    resource: dict[str, Any] = {
        "schemas": [USER_SCHEMA],
        "id": str(user.id),
        "userName": user.email,
        "active": bool(user.is_active),
        "emails": [{"value": user.email, "type": "work", "primary": True}],
        "meta": {
            "resourceType": "User",
            "created": _stamp(user.created_at),
            "lastModified": _stamp(user.updated_at),
            "location": f"{base_url}/scim/v2/Users/{user.id}",
        },
    }
    if user.external_id:
        resource["externalId"] = user.external_id
    if user.name:
        resource["displayName"] = user.name
        resource["name"] = {"formatted": user.name}
    return resource


def list_response(resources: list[dict[str, Any]], total: int, start_index: int) -> dict[str, Any]:
    return {
        "schemas": [LIST_SCHEMA],
        "totalResults": total,
        "startIndex": start_index,
        "itemsPerPage": len(resources),
        "Resources": resources,
    }


def parse_filter(raw: str | None) -> tuple[str, str] | None:
    """Return (attribute, value) for the one supported filter shape, ``<attr> eq "<value>"``; None when no filter."""
    if raw is None or not raw.strip():
        return None
    match = _FILTER.match(raw)
    if match is None:
        raise ScimError(400, 'Only filters of the form userName eq "value" (also externalId and id) are supported', "invalidFilter")
    value = re.sub(r"\\(.)", r"\1", match.group(2))
    attribute = {"username": "userName", "externalid": "externalId", "id": "id"}[match.group(1).lower()]
    return attribute, value


def page_window(start_index: str | None, count: str | None) -> tuple[int, int]:
    """SCIM startIndex is 1-based and values below 1 mean 1; count is capped. Returns (offset, limit)."""
    try:
        start = max(int(start_index), 1) if start_index is not None else 1
        limit = int(count) if count is not None else DEFAULT_PAGE
    except ValueError as exc:
        raise ScimError(400, "startIndex and count must be integers", "invalidValue") from exc
    return start - 1, min(max(limit, 0), MAX_PAGE)


@dataclass(frozen=True)
class UserChanges:
    """What a request wants changed. A key is present only when the request set it; None means 'clear it'."""

    fields: dict[str, Any] = field(default_factory=dict)

    def merged(self, key: str, value: Any) -> "UserChanges":
        return UserChanges({**self.fields, key: value})


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise ScimError(400, "active must be true or false", "invalidValue")


def _text(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ScimError(400, f"{label} must be a string", "invalidValue")
    cleaned = value.strip()
    if len(cleaned) > _NAME_MAX:
        raise ScimError(400, f"{label} is longer than {_NAME_MAX} characters", "invalidValue")
    return cleaned or None


def normalize_email(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScimError(400, "userName is required and must be an email address", "invalidValue")
    try:
        return str(_EMAIL.validate_python(value.strip())).lower()
    except ValidationError as exc:
        raise ScimError(400, "userName must be a valid email address", "invalidValue") from exc


def _display_name(name: Any, display: Any) -> str | None:
    if isinstance(name, dict):
        formatted = _text(name.get("formatted"), "name.formatted")
        if formatted:
            return formatted
        given = _text(name.get("givenName"), "name.givenName")
        family = _text(name.get("familyName"), "name.familyName")
        joined = " ".join(part for part in (given, family) if part)
        if joined:
            return joined[:_NAME_MAX]
    return _text(display, "displayName")


def _refuse_roles(payload: dict[str, Any]) -> None:
    present = [key for key in payload if key.lower() in _ROLE_KEYS and payload[key] not in (None, [], {}, "")]
    if present:
        raise ScimError(400, f"{', '.join(sorted(present))} cannot be set through SCIM; roles are managed in OpenProxyAI", "invalidValue")


def parse_user_payload(payload: Any, *, creating: bool) -> UserChanges:
    """Validate a POST/PUT body into UserChanges. Unknown attributes are ignored (RFC 7643 3.1); roles are refused.

    A new user is active unless told otherwise. A PUT that omits ``active`` leaves it unchanged, so a replace can never
    quietly re-enable someone the identity provider deactivated.
    """
    if not isinstance(payload, dict):
        raise ScimError(400, "Request body must be a JSON object", "invalidSyntax")
    _refuse_roles(payload)
    fields: dict[str, Any] = {
        "email": normalize_email(payload.get("userName")),
        "external_id": _text(payload.get("externalId"), "externalId"),
        "name": _display_name(payload.get("name"), payload.get("displayName")),
    }
    if "active" in payload:
        fields["active"] = _bool(payload["active"])
    elif creating:
        fields["active"] = True
    return UserChanges(fields)


def _changes_from_object(value: Any) -> UserChanges:
    if not isinstance(value, dict):
        raise ScimError(400, "A PATCH operation without a path needs an object value", "invalidValue")
    _refuse_roles(value)
    changes = UserChanges()
    if "active" in value:
        changes = changes.merged("active", _bool(value["active"]))
    if "userName" in value:
        changes = changes.merged("email", normalize_email(value["userName"]))
    if "externalId" in value:
        changes = changes.merged("external_id", _text(value["externalId"], "externalId"))
    if "name" in value or "displayName" in value:
        changes = changes.merged("name", _display_name(value.get("name"), value.get("displayName")))
    return changes


def _changes_from_path(op: str, path: str, value: Any, current: UserChanges) -> UserChanges:
    key = path.strip().lower()
    removing = op == "remove"
    if key.split("[")[0].split(".")[0] in _ROLE_KEYS:
        raise ScimError(400, f"{path} cannot be set through SCIM; roles are managed in OpenProxyAI", "invalidValue")
    if key == "active":
        if removing:
            raise ScimError(400, "active cannot be removed", "mutability")
        return current.merged("active", _bool(value))
    if key == "username":
        if removing:
            raise ScimError(400, "userName cannot be removed", "mutability")
        return current.merged("email", normalize_email(value))
    if key == "externalid":
        return current.merged("external_id", None if removing else _text(value, "externalId"))
    if key in {"displayname", "name.formatted", "name.givenname", "name.familyname"}:
        return current.merged("name", None if removing else _text(value, path))
    if key == "name":
        return current.merged("name", None if removing else _display_name(value, None))
    if key.startswith("emails"):
        return current  # userName is the single source of truth for the email; an emails-only change is accepted and ignored
    raise ScimError(400, f"Unsupported attribute path: {path}", "invalidPath")


def parse_patch(payload: Any) -> UserChanges:
    if not isinstance(payload, dict) or not isinstance(payload.get("Operations"), list) or not payload["Operations"]:
        raise ScimError(400, "PATCH body needs a non-empty Operations list", "invalidSyntax")
    if PATCH_SCHEMA not in (payload.get("schemas") or []):
        raise ScimError(400, f"PATCH body must include the schema {PATCH_SCHEMA}", "invalidSyntax")
    changes = UserChanges()
    for operation in payload["Operations"]:
        if not isinstance(operation, dict):
            raise ScimError(400, "Each operation must be an object", "invalidSyntax")
        op = str(operation.get("op", "")).strip().lower()
        if op not in {"add", "replace", "remove"}:
            raise ScimError(400, "op must be add, replace or remove", "invalidSyntax")
        path = operation.get("path")
        if path in (None, ""):
            if op == "remove":
                raise ScimError(400, "remove needs a path", "noTarget")
            for key, value in _changes_from_object(operation.get("value")).fields.items():
                changes = changes.merged(key, value)
        else:
            changes = _changes_from_path(op, str(path), operation.get("value"), changes)
    return changes
