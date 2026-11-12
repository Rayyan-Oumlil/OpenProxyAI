#!/usr/bin/env python3
"""SCIM 2.0 conformance check on a running stack, the way Okta or Entra would drive it. Standard library only.

    python3 scripts/smoke_scim.py                       # against http://localhost:8000 (the seeded demo)
    BASE_URL=http://host:8000 python3 scripts/smoke_scim.py

Signs in as the seeded admin, creates the org's SCIM token over the admin API, then runs the provisioning lifecycle over
/scim/v2 with that token: discovery documents, create, read, list and filter, PATCH in both the Okta and the Entra
style, PUT, DELETE (deactivation), the SCIM error shape, refusal of roles, isolation from the normal APIs, and the audit
trail. Cleans up after itself (revokes the token and, if it had to switch the demo org to a plan that includes SCIM,
switches it back). Exits 1 if any outcome differs from the contract.
"""

import sys
import uuid

import smoke_lib as lib
from smoke_lib import ADMIN, call, check, login_admin, sql

USER = "urn:ietf:params:scim:schemas:core:2.0:User"
PATCH = "urn:ietf:params:scim:api:messages:2.0:PatchOp"
ERROR = "urn:ietf:params:scim:api:messages:2.0:Error"


def create_token(admin):
    """Returns (token response, plan to restore or None). The demo org starts on a plan without SCIM, so it is switched for the run."""
    status, _, body = call("POST", "/api/v1/scim/token", token=admin)
    if status != 402:
        return status, body, None
    org_clause = f"(SELECT org_id FROM users WHERE email = '{ADMIN[0]}')"
    previous = sql(f"SELECT plan FROM organizations WHERE id = {org_clause}")[0][0]
    sql(f"UPDATE organizations SET plan = 'enterprise' WHERE id = {org_clause}")
    status, _, body = call("POST", "/api/v1/scim/token", token=admin)
    return status, body, previous


def main():
    admin = login_admin()
    status, body, restore_plan = create_token(admin)
    check("admin creates the SCIM token (shown once)", status == 201 and body.get("token", "").startswith("scim_"), (status, body))
    token = body["token"]

    def scim(method, path, payload=None):
        return call(method, "/scim/v2" + path, token=token, body=payload)

    try:
        status, hdr, error = call("GET", "/scim/v2/Users")
        check("no token: 401 with the SCIM error body", status == 401 and error.get("schemas") == [ERROR] and error.get("status") == "401", (status, error))
        check("SCIM responses are application/scim+json", hdr.get("content-type", "").startswith("application/scim+json"), hdr.get("content-type"))
        status, _, _ = call("GET", "/api/v1/users", token=token)
        check("a SCIM token opens nothing outside /scim/v2", status == 401, status)

        status, _, config = scim("GET", "/ServiceProviderConfig")
        check("ServiceProviderConfig: patch yes, bulk no, filter yes", status == 200 and config["patch"]["supported"] and not config["bulk"]["supported"] and config["filter"]["supported"], config)
        status, _, types = scim("GET", "/ResourceTypes")
        check("ResourceTypes lists User only", status == 200 and [r["id"] for r in types["Resources"]] == ["User"], types)
        status, _, schemas = scim("GET", "/Schemas")
        check("Schemas describes User", status == 200 and schemas["Resources"][0]["id"] == USER, schemas)
        status, _, groups = scim("GET", "/Groups")
        check("Groups: honest 404 in the SCIM shape", status == 404 and groups.get("schemas") == [ERROR], (status, groups))

        address = f"scim-smoke-{uuid.uuid4().hex[:8]}@example.com"
        status, hdr, user = scim("POST", "/Users", {"schemas": [USER], "userName": address.upper(), "name": {"givenName": "Smoke", "familyName": "User"}, "externalId": "smoke-ext", "active": True})
        check("create: 201, lower-cased userName, Location header", status == 201 and user.get("userName") == address and hdr.get("location", "").endswith(f"/scim/v2/Users/{user.get('id')}"), (status, user))
        uid = user["id"]
        status, _, again = scim("POST", "/Users", {"userName": address})
        check("create again: 409 uniqueness", status == 409 and again.get("scimType") == "uniqueness", (status, again))
        status, _, roles = scim("POST", "/Users", {"userName": f"r-{address}", "roles": [{"value": "admin"}]})
        check("roles in a create are refused (SCIM cannot grant admin)", status == 400 and roles.get("scimType") == "invalidValue", (status, roles))

        status, _, found = scim("GET", "/Users?filter=" + f'userName eq "{address}"'.replace(" ", "%20").replace('"', "%22"))
        check("filter userName eq finds exactly the user", status == 200 and found["totalResults"] == 1 and found["Resources"][0]["id"] == uid, (status, found))
        status, _, bad = scim("GET", "/Users?filter=userName%20co%20%22x%22")
        check("unsupported filter: 400 invalidFilter", status == 400 and bad.get("scimType") == "invalidFilter", (status, bad))

        status, _, off = scim("PATCH", f"/Users/{uid}", {"schemas": [PATCH], "Operations": [{"op": "replace", "value": {"active": False}}]})
        check("PATCH (Okta style) deactivates", status == 200 and off["active"] is False, (status, off))
        status, _, on = scim("PATCH", f"/Users/{uid}", {"schemas": [PATCH], "Operations": [{"op": "Replace", "path": "active", "value": "True"}]})
        check("PATCH (Entra style, string boolean) reactivates", status == 200 and on["active"] is True, (status, on))
        status, _, put = scim("PUT", f"/Users/{uid}", {"schemas": [USER], "userName": address, "displayName": "Replaced"})
        check("PUT replaces attributes and leaves active alone", status == 200 and put["displayName"] == "Replaced" and put["active"] is True and "externalId" not in put, (status, put))
        status, _, role_patch = scim("PATCH", f"/Users/{uid}", {"schemas": [PATCH], "Operations": [{"op": "replace", "path": "roles", "value": "admin"}]})
        check("roles in a PATCH are refused", status == 400, (status, role_patch))

        status, _, _ = scim("DELETE", f"/Users/{uid}")
        check("DELETE: 204", status == 204, status)
        status, _, gone = scim("GET", f"/Users/{uid}")
        check("DELETE deactivates and keeps the row", status == 200 and gone["active"] is False, (status, gone))
        status, _, missing = scim("GET", f"/Users/{uuid.uuid4()}")
        check("unknown id: 404 in the SCIM shape", status == 404 and missing.get("schemas") == [ERROR], (status, missing))

        _, _, log = call("GET", "/api/v1/admin/audit-log?page_size=100&resource_type=user", token=admin)
        mine = [e for e in log.get("items", []) if e.get("resource_id") == uid]
        actions = {e["action"] for e in mine}
        check("every change is in the audit log, actor is the token", {"user.scim_created", "user.scim_deactivated", "user.scim_reactivated", "user.scim_updated"} <= actions and all(e["actor_email"].startswith("scim:scim_") for e in mine), actions)
        check("the token itself is not in the audit log", token not in str(log), "token found in the log")

        status, _, rotated = call("POST", "/api/v1/scim/token", token=admin)
        status_old, _, _ = scim("GET", "/Users")
        check("rotating the token stops the old one at once", status == 201 and rotated["rotated"] is True and status_old == 401, (status, status_old))
        token = rotated["token"]
    finally:
        call("DELETE", "/api/v1/scim/token", token=admin)
        status, _, _ = scim("GET", "/Users")
        check("revoking the token stops it at once", status == 401, status)
        if restore_plan is not None:
            sql(f"UPDATE organizations SET plan = '{restore_plan}' WHERE id = (SELECT org_id FROM users WHERE email = '{ADMIN[0]}')")

    print(f"\n{lib.failures} failure(s)" if lib.failures else "\nSCIM smoke passed")
    return 1 if lib.failures else 0


if __name__ == "__main__":
    sys.exit(main())
