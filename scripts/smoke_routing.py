#!/usr/bin/env python3
"""Checks classification-aware routing on a running seeded demo, the way an admin and a client would use it.

Standard library only. Run by scripts/smoke.sh after the stack is up; also runnable on its own:

    python3 scripts/smoke_routing.py            # against http://localhost:8000
    BASE_URL=http://host:8000 python3 scripts/smoke_routing.py

It registers two models, walks the routing modes (off, log_only, enforce), and always restores the demo
(routing off, registry emptied, the provider key's class put back) so it can be run repeatedly.
Exits 1 if any outcome differs from what routing should produce.
"""

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
ADMIN = (os.environ.get("ADMIN_EMAIL", "admin@example.com"), os.environ.get("ADMIN_PASSWORD", "DemoPass123!"))
CLIENT_KEY = os.environ.get("API_KEY", "opai_dev_demo0001_00000000000000000000000000demo01fea5")

failures = 0


def call(method, path, *, token=None, body=None, headers=None):
    """Returns (status, response headers (lower-cased), parsed JSON or raw text)."""
    request = urllib.request.Request(
        BASE + path, method=method, data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {}), **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status, raw, got = response.status, response.read().decode(), dict(response.headers)
    except urllib.error.HTTPError as error:
        status, raw, got = error.code, error.read().decode(), dict(error.headers)
    try:
        parsed = json.loads(raw)
    except ValueError:
        parsed = raw
    return status, {k.lower(): v for k, v in got.items()}, parsed


def check(label, ok, detail=""):
    global failures
    if not ok:
        failures += 1
    print(f"{'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"   [{str(detail)[:200]}]"))


def main():
    status, _, tokens = call("POST", "/api/v1/auth/login", body={"email": ADMIN[0], "password": ADMIN[1]})
    admin = tokens["access_token"]

    def policy(**fields):
        return call("PATCH", "/api/v1/organizations/current/policy", token=admin, body=fields)

    def chat(content="hello", model="openai/gpt-4o-mini", data_class=None, **extra):
        headers = {"x-openproxy-data-class": data_class} if data_class else {}
        return call("POST", "/v1/chat/completions", token=CLIENT_KEY, headers=headers,
                    body={"model": model, "messages": [{"role": "user", "content": content}], **extra})

    _, _, existing = call("GET", "/api/v1/model-registry", token=admin)
    if existing:
        sys.exit("The model registry is not empty. This script is for the seeded demo and needs an empty registry "
                 "(docker compose -f docker-compose.demo.yml down -v resets it).")
    _, _, keys = call("GET", "/api/v1/provider-keys", token=admin)
    key = keys[0]
    original_class = key["max_data_class"]
    created = []
    try:
        print("-- provider keys and the registry")
        check("provider keys expose api_base, max_data_class, is_internal", {"api_base", "max_data_class", "is_internal"} <= set(key), key)
        call("PATCH", f"/api/v1/provider-keys/{key['id']}", token=admin, body={"max_data_class": "confidential"})
        status, _, body = policy(routing_mode="enforce")
        check("enforcing with an empty registry is refused (409)", status == 409 and body["detail"]["error"] == "empty_registry", body)

        for model, data_class, cost in (("openai/gpt-4o-mini", "internal", "low"), ("openai/gpt-4o", "confidential", "high")):
            status, _, body = call("POST", "/api/v1/model-registry", token=admin, body={
                "model_id": model, "provider_key_id": key["id"], "max_data_class": data_class, "regions": ["us"],
                "capabilities": ["VISION"], "cost_tier": cost})
            check(f"register {model} ({data_class})", status == 201, body)
            if status == 201:
                created.append(body["id"])
        status, _, body = call("POST", "/api/v1/model-registry", token=admin, body={
            "model_id": "openai/gpt-4.1", "provider_key_id": key["id"], "max_data_class": "secret", "regions": ["us"]})
        check("a model cannot be cleared above its key (422)", status == 422, body)

        print("-- log_only records and never refuses")
        check("log_only accepted", policy(routing_mode="log_only")[0] == 200)
        status, headers, body = chat(data_class="secret")
        check("a secret request is still served", status == 200, body)
        check("the decision is reported", headers.get("x-openproxyai-route-reason") == "not_authorized:class_too_low", headers)

        print("-- enforce")
        check("enforce accepted", policy(routing_mode="enforce")[0] == 200)
        status, headers, body = chat()
        check("an authorized request is served", status == 200 and headers.get("x-openproxyai-route-model") == "openai/gpt-4o-mini", body)
        status, _, body = chat(data_class="confidential")
        check("too sensitive for the model: 446 routing_blocked", status == 446 and body.get("error") == "routing_blocked", body)
        status, _, body = chat(model="openai/gpt-4o", data_class="confidential")
        check("the model cleared for it serves it", status == 200, body)
        status, _, body = chat(model="openai/gpt-4o", data_class="secret")
        check("nothing is cleared for secret: 446", status == 446, body)
        status, _, body = chat(model="openai/gpt-4o-mini-2024-07-18")
        check("a model missing from the registry: 446", status == 446 and body.get("route_reason") == "not_in_registry", body)
        status, headers, _ = chat(model="cap:VISION", data_class="confidential")
        check("cap:VISION with confidential data routes to the cleared model", status == 200 and headers.get("x-openproxyai-route-model") == "openai/gpt-4o", headers)
        status, headers, _ = chat(model="cap:VISION")
        check("cap:VISION with internal data routes to the cheaper model", headers.get("x-openproxyai-route-model") == "openai/gpt-4o-mini", headers)
        check("streaming is served", chat(stream=True)[0] == 200)
        check("an unregistered embedding model is refused", call("POST", "/v1/embeddings", token=CLIENT_KEY, body={"model": "openai/text-embedding-3-small", "input": "hi"})[0] == 446)

        print("-- the audit trail and the playground")
        status, _, logs = call("GET", "/api/v1/analytics/logs?limit=50", token=admin)
        refused = [row for row in logs["items"] if (row.get("error_message") or "") == "policy_blocked:no_authorized_model"]
        check("refused requests are in the audit log", len(refused) >= 3, f"{len(refused)} rows")
        if refused:
            _, _, detail = call("GET", f"/api/v1/analytics/logs/{refused[0]['id']}", token=admin)
            meta = detail.get("request_metadata") or {}
            check("a refused row carries its routing decision and data class", "routing" in meta and "data_class" in meta, meta)
        status, _, body = call("POST", "/api/v1/playground/compare", token=admin, body={
            "models": ["openai/gpt-4o", "openai/gpt-4o-mini-2024-07-18"], "messages": [{"role": "user", "content": "hello"}]})
        results = {r["model"]: r for r in body.get("results", [])} if status == 200 else {}
        check("playground: a registered model answers", results.get("openai/gpt-4o", {}).get("error") is None, body)
        check("playground: an unregistered model is refused, not called", "not_in_registry" in (results.get("openai/gpt-4o-mini-2024-07-18", {}).get("error") or ""), body)
    finally:
        policy(routing_mode="off")
        for entry_id in created:
            call("DELETE", f"/api/v1/model-registry/{entry_id}", token=admin)
        call("PATCH", f"/api/v1/provider-keys/{key['id']}", token=admin, body={"max_data_class": original_class})
        check("restored: routing off, the unregistered model works again", chat(model="openai/gpt-4o-mini")[0] == 200)

    if failures:
        print(f"{failures} routing check(s) failed")
        sys.exit(1)
    print("routing smoke passed")


if __name__ == "__main__":
    main()
