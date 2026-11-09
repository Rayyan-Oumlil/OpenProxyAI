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
import time
import urllib.error
import urllib.request

BASE = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
FAKE_URL = os.environ.get("FAKE_URL", "http://localhost:9090").rstrip("/")  # the demo's fake upstream, which records who called it
CUSTOM_KEY = "sk-smoke-custom-endpoint"
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


def settled_log_total(admin):
    """The audit-log count once background writes from earlier requests have landed (two equal readings in a row)."""
    previous = None
    for _ in range(40):
        _, _, logs = call("GET", "/api/v1/analytics/logs?limit=1", token=admin)
        if logs["total"] == previous:
            return previous
        previous = logs["total"]
        time.sleep(0.5)
    return previous


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
    created = []
    custom_key_id = None
    try:
        print("-- custom endpoints: validated when saved, guarded when used")
        base = {"provider": "openai", "api_key": CUSTOM_KEY, "key_alias": "smoke-custom-endpoint"}
        for label, extra in (
            ("cloud metadata address", {"api_base": "http://169.254.169.254/latest", "is_internal": True}),
            ("a public endpoint over http", {"api_base": "http://8.8.8.8/v1"}),
            ("a private endpoint not marked internal", {"api_base": "https://10.0.0.5/v1"}),
            ("credentials in the URL", {"api_base": "https://user:pw@8.8.8.8/v1"}),
            ("a provider that cannot be guarded", {"provider": "anthropic", "api_base": "https://8.8.8.8/v1"}),
        ):
            status, _, body = call("POST", "/api/v1/provider-keys", token=admin, body={**base, **extra})
            check(f"refused at save: {label} (422)", status == 422 and body["detail"]["error"] == "invalid_api_base", body)

        status, _, key = call("POST", "/api/v1/provider-keys", token=admin, body={
            **base, "api_base": "http://fake-llm:9090/v1", "is_internal": True, "max_data_class": "confidential", "weight": 1})
        check("an internal OpenAI-compatible endpoint is accepted", status == 201 and key["api_base"] == "http://fake-llm:9090/v1", key)
        custom_key_id = key["id"]

        print("-- the registry")
        check("provider keys expose api_base, max_data_class, is_internal", {"api_base", "max_data_class", "is_internal"} <= set(key), key)
        status, _, body = policy(routing_mode="enforce")
        check("enforcing with an empty registry is refused (409)", status == 409 and body["detail"]["error"] == "empty_registry", body)

        for model, data_class, cost in (("openai/gpt-4o-mini", "internal", "low"), ("openai/gpt-4o", "confidential", "high")):
            status, _, body = call("POST", "/api/v1/model-registry", token=admin, body={
                "model_id": model, "provider_key_id": custom_key_id, "max_data_class": data_class, "regions": ["us"],
                "capabilities": ["VISION"], "cost_tier": cost})
            check(f"register {model} ({data_class})", status == 201, body)
            if status == 201:
                created.append(body["id"])
        status, _, body = call("POST", "/api/v1/model-registry", token=admin, body={
            "model_id": "openai/gpt-4.1", "provider_key_id": custom_key_id, "max_data_class": "secret", "regions": ["us"]})
        check("a model cannot be cleared above its key (422)", status == 422, body)

        print("-- log_only records and never refuses")
        check("log_only accepted", policy(routing_mode="log_only")[0] == 200)
        status, headers, body = chat(data_class="secret")
        check("a secret request is still served", status == 200, body)
        check("the decision is reported", headers.get("x-openproxyai-route-reason") == "not_authorized:class_too_low", headers)

        print("-- enforce")
        check("enforce accepted", policy(routing_mode="enforce")[0] == 200)
        # A prompt nobody has sent before, so the answer cannot come from the cache and the upstream must be called.
        prompt = f"credential check {os.getpid()}-{os.urandom(4).hex()}"
        status, headers, body = chat(prompt)
        check("an authorized request is served", status == 200 and headers.get("x-openproxyai-route-model") == "openai/gpt-4o-mini", body)
        try:
            calls = json.loads(urllib.request.urlopen(f"{FAKE_URL}/__calls", timeout=10).read())
            mine = [c for c in calls if c["body"]["messages"][-1]["content"] == prompt]
            check("it reached the endpoint through the key's own credentials, not the demo key",
                  len(mine) == 1 and mine[0]["authorization"] == f"Bearer {CUSTOM_KEY}", mine)
        except OSError as error:
            print(f"skip (fake upstream not reachable at {FAKE_URL}: {error})")
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

        print("-- the policy preview agrees with reality and leaves no trace")
        scenarios = (("openai/gpt-4o-mini", None), ("openai/gpt-4o-mini", "confidential"), ("openai/gpt-4o", "confidential"),
                     ("openai/gpt-4o", "secret"), ("openai/gpt-4o-mini-2024-07-18", None), ("cap:VISION", "confidential"), ("cap:AUDIO", None))
        total_before = settled_log_total(admin)
        previews = []
        for model, data_class in scenarios:
            status, _, preview = call("POST", "/api/v1/policy/preview", token=admin, body={
                "model": model, "messages": [{"role": "user", "content": "preview check"}], **({"data_class": data_class} if data_class else {})})
            previews.append((model, data_class, preview))
            check(f"preview answers for {model} / {data_class or 'default class'}", status == 200, preview)
        total_after = settled_log_total(admin)
        check("previews wrote no audit rows", total_after == total_before, (total_before, total_after))
        for model, data_class, preview in previews:
            actual_status, actual_headers, actual_body = chat("preview check", model=model, data_class=data_class)
            if preview["verdict"] == "allowed":
                agrees = actual_status == 200 and actual_headers.get("x-openproxyai-route-model") == preview["routing"]["model"]
            else:
                agrees = preview["verdict"] == "blocked_by_routing" and actual_status == 446 and actual_body.get("route_reason") == preview["routing"]["reason"]
            check(f"the real request did what the preview said: {model} / {data_class or 'default class'} ({preview['verdict']})", agrees, (actual_status, actual_body))

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
        if custom_key_id:
            call("DELETE", f"/api/v1/provider-keys/{custom_key_id}", token=admin)
        check("restored: routing off, the unregistered model works again", chat(model="openai/gpt-4o-mini")[0] == 200)

    if failures:
        print(f"{failures} routing check(s) failed")
        sys.exit(1)
    print("routing smoke passed")


if __name__ == "__main__":
    main()
