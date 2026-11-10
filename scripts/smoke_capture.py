#!/usr/bin/env python3
"""Checks opt-in payload capture on a running seeded demo: what is stored, what never is, and that expiry works.

Standard library only. Run by scripts/smoke.sh after the stack is up; also runnable on its own:

    python3 scripts/smoke_capture.py            # against http://localhost:8000

Reads the stored rows back from Postgres through `docker compose exec`, and runs the real purge job inside the API
container. Restores the demo's policy (sample rate 0, enforcement mode) when it finishes. Exits 1 on any difference.
"""

import json
import subprocess
import sys
import time
import urllib.request

import smoke_lib as lib
from smoke_lib import BASE, CLIENT_KEY, COMPOSE, call, check, login_admin, sql


def stored(request_id):
    """[messages json, output, redacted, days until expiry] for one request, or []."""
    return sql(
        "SELECT messages::text, output, redacted::text, round((extract(epoch FROM (expires_at - now())) / 86400)::numeric, 1) "
        f"FROM request_payloads WHERE request_id = '{request_id}'"
    )


def chat(content, headers=None):
    status, got, _ = call(
        "POST", "/v1/chat/completions", token=CLIENT_KEY, headers=headers,
        body={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": content}]},
    )
    return status, got.get("x-openproxyai-request-id", "")


def chat_stream(content):
    """A streamed chat request, read to the end like a client would. Returns (status, request id, the streamed text)."""
    request = urllib.request.Request(
        BASE + "/v1/chat/completions", method="POST",
        data=json.dumps({"model": "openai/gpt-4o-mini", "stream": True, "messages": [{"role": "user", "content": content}]}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {CLIENT_KEY}"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read().decode()
        return response.status, response.headers.get("x-openproxyai-request-id", ""), body


def wait_for_row(request_id):
    """Capture runs in the background, so poll briefly."""
    for _ in range(30):
        rows = stored(request_id)
        if rows:
            return rows
        time.sleep(0.5)
    return []


def main():
    admin = login_admin()
    _, _, original = call("GET", "/api/v1/organizations/current/policy", token=admin)

    def set_policy(**fields):
        status, _, parsed = call("PATCH", "/api/v1/organizations/current/policy", token=admin, body=fields)
        assert status == 200, (status, parsed)

    try:
        set_policy(payload_capture_sample_rate=0, enforcement_mode="log_only")
        status, rid = chat(f"off by default {time.time()}")
        time.sleep(3)
        check("at the default rate of 0 nothing is stored", status == 200 and stored(rid) == [], (status, stored(rid)))

        set_policy(payload_capture_sample_rate=1)
        marker = f"capture smoke {time.time()}"
        status, rid = chat(f"{marker}. Please mail jane.doe@example.com")
        rows = wait_for_row(rid)
        check("opted in at rate 1: the request is stored", status == 200 and len(rows) == 1, (status, rows))
        if rows:
            messages, output, redacted, days = rows[0]
            check("the stored prompt kept its text", marker in messages, messages)
            check("the email address is not in the stored prompt, and the row says it was redacted",
                  "jane.doe@example.com" not in messages and "[REDACTED]" in messages and redacted == "true", (messages, redacted))
            check("an answer was stored", len(output) > 0, output)
            check("the free plan keeps it 7 days", abs(float(days) - 7.0) < 0.2, days)

        status, rid_secret = chat(f"classified {time.time()}", headers={"x-openproxy-data-class": "confidential"})
        time.sleep(3)
        check("a confidential request is never stored, even at rate 1", status == 200 and stored(rid_secret) == [], (status, stored(rid_secret)))

        # Expiry: age one row, leave another, run the real purge job inside the API container.
        status, rid_keep = chat(f"keep me {time.time()}")
        wait_for_row(rid_keep)
        sql(f"UPDATE request_payloads SET expires_at = now() - interval '1 day' WHERE request_id = '{rid}'")
        purge = subprocess.run(
            [*COMPOSE, "exec", "-T", "api", "python", "-c",
             "import asyncio; from app.services.payload_capture import purge_expired_payloads; print('PURGED', asyncio.run(purge_expired_payloads()))"],
            capture_output=True, text=True,
        )
        check("the purge job deletes the expired row and reports it", "PURGED 1" in purge.stdout, (purge.stdout[-200:], purge.stderr[-200:]))
        check("the expired row is gone and the live one is kept", stored(rid) == [] and len(stored(rid_keep)) == 1, (stored(rid), stored(rid_keep)))

        marker_stream = f"streamed capture {time.time()}"
        status, rid_stream, body = chat_stream(marker_stream)
        rows = wait_for_row(rid_stream)
        check("a streamed request is stored too, with the text that was streamed",
              status == 200 and "[DONE]" in body and len(rows) == 1 and marker_stream in rows[0][0] and len(rows[0][1]) > 0, (status, rows))

        status, _, parsed = call("PATCH", "/api/v1/organizations/current/policy", token=admin, body={"payload_capture_sample_rate": 1.5})
        check("a rate above 1 is rejected (422)", status == 422, (status, parsed))
    finally:
        restore = {k: original[k] for k in ("payload_capture_sample_rate", "enforcement_mode") if k in original}
        call("PATCH", "/api/v1/organizations/current/policy", token=admin, body=restore)
        sql("DELETE FROM request_payloads")

    if lib.failures:
        print(f"{lib.failures} capture check(s) failed")
        sys.exit(1)
    print("capture smoke passed")


if __name__ == "__main__":
    main()
