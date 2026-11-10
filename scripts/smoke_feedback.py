#!/usr/bin/env python3
"""Checks POST /v1/feedback on a running seeded demo, the way an application would use it.

Standard library only. Run by scripts/smoke.sh after the stack is up; also runnable on its own:

    python3 scripts/smoke_feedback.py            # against http://localhost:8000
    BASE_URL=http://host:8000 python3 scripts/smoke_feedback.py

It sends one real chat request, rates it with the id from the response header, and reads the stored row back from
Postgres through `docker compose exec` (the demo stack's database). Exits 1 if any outcome differs from the contract.
"""

import sys
import time
import uuid

import smoke_lib as lib
from smoke_lib import CLIENT_KEY, call, check, sql


def second_org_key():
    """(a new API key of a different organization, a function that revokes it). The org is registered on the first run, signed into after."""
    login = {"email": "feedback-smoke-b@example.com", "password": "Smoke-Other-Org-1!"}
    status, _, tokens = call("POST", "/api/v1/auth/register", body={**login, "name": "Other Org", "org_name": "Feedback Smoke Other Org"})
    if status != 200:
        status, _, tokens = call("POST", "/api/v1/auth/login", body=login)
    admin = tokens["access_token"]
    status, _, key = call("POST", "/api/v1/api-keys", token=admin, body={"name": f"smoke-{uuid.uuid4().hex[:8]}"})
    if status != 201:
        raise SystemExit(f"could not create the second organization's key: {status} {key}")
    return key["key"], lambda: call("DELETE", f"/api/v1/api-keys/{key['id']}", token=admin)


def is_uuid(text):
    try:
        uuid.UUID(text)
        return True
    except ValueError:
        return False


def stored_rows(request_id):
    """(score_name, value, source, comment) rows for one request, straight from the database."""
    return [tuple(row) for row in sql(
        "SELECT score_name, value::float8, source, coalesce(comment, '<none>') FROM request_scores "
        f"WHERE request_id = '{request_id}' ORDER BY score_name"
    )]


def rate(request_id, body):
    """POST feedback; the request log is written in the background, so give it a moment to land."""
    for _ in range(40):
        status, _, parsed = call("POST", "/v1/feedback", token=CLIENT_KEY, body={"request_id": request_id, **body})
        if status != 404:
            return status, parsed
        time.sleep(0.5)
    return status, parsed


def main():
    status, headers, _ = call(
        "POST", "/v1/chat/completions", token=CLIENT_KEY,
        body={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": f"feedback smoke {time.time()}"}]},
    )
    request_id = headers.get("x-openproxyai-request-id", "")
    check("a chat request succeeds and returns its request id", status == 200 and is_uuid(request_id), (status, headers))

    check("feedback without a key is refused (401)", call("POST", "/v1/feedback", body={"request_id": request_id, "thumbs": "up"})[0] == 401)

    status, parsed = rate(request_id, {"thumbs": "up"})
    check("thumbs up is accepted using the response header's id", status == 200 and parsed.get("value") == 1.0, (status, parsed))

    status, parsed = rate(request_id, {"thumbs": "down", "comment": "wrong, mail jane.doe@example.com"})
    check("the same rating again replaces it (200)", status == 200 and parsed.get("value") == 0.0, (status, parsed))

    status, _ = rate(request_id, {"score_name": "coherence", "value": 4.5})
    check("a numeric score with its own name is accepted", status == 200)

    rows = stored_rows(request_id)
    thumbs = [r for r in rows if r[0] == "thumbs"]
    check("one row per score name: thumbs replaced, coherence added", [r[0] for r in rows] == ["coherence", "thumbs"], rows)
    check("the stored thumbs value is the latest (0), from the api source", thumbs and thumbs[0][1] == "0" and thumbs[0][2] == "api", thumbs)
    check("the comment is stored without the email address", thumbs and "jane.doe@example.com" not in thumbs[0][3] and "[REDACTED]" in thumbs[0][3], thumbs)

    other_key, revoke_other_key = second_org_key()
    status, _, other = call("POST", "/v1/feedback", token=other_key, body={"request_id": request_id, "thumbs": "up"})
    status_unknown, _, unknown = call("POST", "/v1/feedback", token=other_key, body={"request_id": str(uuid.uuid4()), "thumbs": "up"})
    check("another organization's key cannot rate this request, and gets the same 404 as for an unknown id",
          status == status_unknown == 404 and other == unknown, (status, other, status_unknown, unknown))
    check("that attempt changed nothing", stored_rows(request_id) == rows, stored_rows(request_id))
    revoked, _, _ = revoke_other_key()
    check("the second organization's key was revoked again", revoked in (200, 204), revoked)

    status, _, parsed = call("POST", "/v1/feedback", token=CLIENT_KEY, body={"request_id": "00000000-0000-4000-8000-000000000000", "thumbs": "up"})
    check("an unknown request id is a 404", status == 404 and parsed.get("error") == "request_not_found", (status, parsed))

    status, _, _ = call("POST", "/v1/feedback", token=CLIENT_KEY, body={"request_id": request_id, "value": 1})
    check("a numeric value without a score_name is a 422", status == 422, status)

    if lib.failures:
        print(f"{lib.failures} feedback check(s) failed")
        sys.exit(1)
    print("feedback smoke passed")


if __name__ == "__main__":
    main()
