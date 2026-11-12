"""SCIM discovery documents: ServiceProviderConfig, ResourceTypes, Schemas (RFC 7643 section 5 to 7)."""

from __future__ import annotations

from typing import Any

from app.services.scim_resources import MAX_PAGE, USER_SCHEMA

_LIST = "urn:ietf:params:scim:api:messages:2.0:ListResponse"


def _attr(name: str, type_: str = "string", **extra: Any) -> dict[str, Any]:
    return {
        "name": name,
        "type": type_,
        "multiValued": False,
        "required": False,
        "mutability": "readWrite",
        "returned": "default",
        "uniqueness": "none",
        **extra,
    }


def service_provider_config(base_url: str) -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
        "documentationUri": "https://docs.openproxyai.com/docs/guides/configuring-scim",
        "patch": {"supported": True},
        "bulk": {"supported": False, "maxOperations": 0, "maxPayloadSize": 0},
        "filter": {"supported": True, "maxResults": MAX_PAGE},
        "changePassword": {"supported": False},
        "sort": {"supported": False},
        "etag": {"supported": False},
        "authenticationSchemes": [
            {
                "type": "oauthbearertoken",
                "name": "SCIM bearer token",
                "description": "A per-organization token created in the admin console (Organization settings).",
                "primary": True,
            }
        ],
        "meta": {"resourceType": "ServiceProviderConfig", "location": f"{base_url}/scim/v2/ServiceProviderConfig"},
    }


def resource_types(base_url: str) -> dict[str, Any]:
    user = {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ResourceType"],
        "id": "User",
        "name": "User",
        "endpoint": "/Users",
        "description": "A person who can sign in to the admin console. Groups are not supported.",
        "schema": USER_SCHEMA,
        "meta": {"resourceType": "ResourceType", "location": f"{base_url}/scim/v2/ResourceTypes/User"},
    }
    return {"schemas": [_LIST], "totalResults": 1, "startIndex": 1, "itemsPerPage": 1, "Resources": [user]}


def user_schema(base_url: str) -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Schema"],
        "id": USER_SCHEMA,
        "name": "User",
        "description": "User account. userName is the email address. Roles are not provisioned through SCIM.",
        "attributes": [
            _attr("userName", required=True, uniqueness="server", caseExact=False),
            _attr("externalId", caseExact=True),
            _attr("displayName"),
            _attr(
                "name",
                "complex",
                subAttributes=[_attr("formatted"), _attr("givenName"), _attr("familyName")],
            ),
            _attr("active", "boolean"),
            _attr(
                "emails",
                "complex",
                multiValued=True,
                subAttributes=[_attr("value"), _attr("type"), _attr("primary", "boolean")],
            ),
        ],
        "meta": {"resourceType": "Schema", "location": f"{base_url}/scim/v2/Schemas/{USER_SCHEMA}"},
    }


def schemas(base_url: str) -> dict[str, Any]:
    return {"schemas": [_LIST], "totalResults": 1, "startIndex": 1, "itemsPerPage": 1, "Resources": [user_schema(base_url)]}
