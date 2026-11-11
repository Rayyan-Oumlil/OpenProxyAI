#!/usr/bin/env python3
"""Checks conversations on a running seeded demo: history is data too, so a model is sent only the turns it is cleared for.

Standard library only. Run by scripts/smoke.sh after the stack is up; also runnable on its own:

    python3 scripts/smoke_conversations.py            # against http://localhost:8000

It registers a model cleared for confidential data and one cleared for internal data, holds a conversation across both,
and reads the fake upstream's record of what each one really received. It always restores the demo.
"""

import json
import os
import sys
import urllib.request

from smoke_lib import BASE, call, check, login_admin  # noqa: F401  (BASE is read by call)
import smoke_lib

FAKE_URL = os.environ.get("FAKE_URL", "http://localhost:9090").rstrip("/")
SECRET_FACT = f"Project Falcon closes at {os.urandom(3).hex()} million"
HIGH, LOW = "openai/gpt-4o", "openai/gpt-4o-mini"


def upstream_saw(text):
    calls = json.loads(urllib.request.urlopen(f"{FAKE_URL}/__calls", timeout=10).read())
    return [c for c in calls if text in json.dumps(c["body"]["messages"])]


def main():
    admin = login_admin()
    _, _, existing = call("GET", "/api/v1/model-registry", token=admin)
    if existing:
        sys.exit("The model registry is not empty. This script is for the seeded demo (docker compose down -v resets it).")
    policy = lambda **fields: call("PATCH", "/api/v1/organizations/current/policy", token=admin, body=fields)  # noqa: E731
    say = lambda cid, content, model, **extra: call(  # noqa: E731
        "POST", f"/api/v1/conversations/{cid}/turns", token=admin, body={"content": content, "model": model, **extra})
    created, conversation, key_id = [], None, None
    try:
        status, _, key = call("POST", "/api/v1/provider-keys", token=admin, body={
            "provider": "openai", "api_key": "sk-smoke-conv", "key_alias": "smoke-conversations", "api_base": "http://fake-llm:9090/v1",
            "is_internal": True, "max_data_class": "confidential", "weight": 1})
        check("a key for the fake upstream", status == 201, key)
        key_id = key["id"]
        for model, level in ((HIGH, "confidential"), (LOW, "internal")):
            status, _, body = call("POST", "/api/v1/model-registry", token=admin, body={
                "model_id": model, "provider_key_id": key_id, "max_data_class": level, "regions": ["us"]})
            check(f"register {model} ({level})", status == 201, body)
            created.append(body.get("id"))

        print("-- opt-in")
        status, _, body = call("POST", "/api/v1/conversations", token=admin, body={"title": "x"})
        check("conversations are off until the org turns them on (403)", status == 403 and body["detail"]["error"] == "conversations_disabled", body)
        check("enforce + conversations accepted", policy(routing_mode="enforce", conversations_enabled=True)[0] == 200)

        print("-- one conversation across two models")
        status, _, conversation = call("POST", "/api/v1/conversations", token=admin, body={"title": "smoke", "tags": ["Smoke"]})
        check("conversation created, private, tags normalised", status == 201 and conversation["visibility"] == "private" and conversation["tags"] == ["smoke"], conversation)
        cid = conversation["id"]

        status, _, first = say(cid, SECRET_FACT, HIGH, data_class="confidential")
        check("a confidential message is answered by the model cleared for it", status == 201 and first["context"]["data_class"] == "confidential", first)
        status, _, second = say(cid, "Now write one friendly sentence about spring.", LOW)
        check("the same conversation continues on the internal-only model", status == 201, second)
        withheld = second["context"]["withheld"] if status == 201 else []
        check("the confidential exchange is listed as held back", sorted(w["seq"] for w in withheld) == [1, 2] and {w["reason"] for w in withheld} == {"above_clearance"}, withheld)
        check("the first model received the confidential text", len(upstream_saw(SECRET_FACT)) >= 1)
        saw = [c for c in upstream_saw(SECRET_FACT)]
        check("the internal-only model did not: only the first call carried it", len(saw) == 1 and saw[0]["body"]["model"].endswith("gpt-4o"), [c["body"]["model"] for c in saw])

        status, _, third = say(cid, "And a second sentence?", HIGH)
        check("switching back sees the whole history again", status == 201 and third["context"]["withheld"] == [] and len(third["context"]["included_turn_ids"]) == 4, third)

        print("-- the record of what was sent")
        status, _, context = call("GET", f"/api/v1/conversations/{cid}/turns/{second['assistant_turn']['id']}/context", token=admin)
        check("what was sent is recorded with a fingerprint", status == 200 and len(context["payload_sha256"]) == 64 and context["model"] == LOW, context)

        print("-- refusals")
        status, _, body = say(cid, SECRET_FACT, LOW, data_class="confidential")
        check("a message above the model's clearance is refused (446), not answered blind", status == 446, body)
        status, _, body = say(cid, "hello", "openai/not-registered")
        check("an unregistered model is refused (446)", status == 446, body)
        _, _, turns = call("GET", f"/api/v1/conversations/{cid}/turns", token=admin)
        check("refused messages stored nothing", len(turns) == 6, len(turns))
        check("an invalid model name is rejected (422)", say(cid, "hi", "cap:VISION")[0] == 422)

        print("-- privacy inside the org")
        _, _, listed = call("GET", "/api/v1/conversations?scope=org", token=admin)
        check("an admin sees titles and sizes for the whole org", any(c["id"] == cid and c["turn_count"] == 6 for c in listed) and "Falcon" not in json.dumps(listed))

        print("-- deletion")
        check("the owner deletes it (204)", call("DELETE", f"/api/v1/conversations/{cid}", token=admin)[0] == 204)
        conversation = None
        check("and it is gone (404)", call("GET", f"/api/v1/conversations/{cid}", token=admin)[0] == 404)
    finally:
        policy(routing_mode="off", conversations_enabled=False)
        if conversation:
            call("DELETE", f"/api/v1/conversations/{conversation['id']}", token=admin)
        for entry_id in created:
            if entry_id:
                call("DELETE", f"/api/v1/model-registry/{entry_id}", token=admin)
        if key_id:
            call("DELETE", f"/api/v1/provider-keys/{key_id}", token=admin)
        check("restored: conversations off again", call("POST", "/api/v1/conversations", token=admin, body={"title": "x"})[0] == 403)

    if smoke_lib.failures:
        print(f"{smoke_lib.failures} conversation check(s) failed")
        sys.exit(1)
    print("conversations smoke passed")


if __name__ == "__main__":
    main()
