#!/usr/bin/env python3
"""Checks the routing quality signal on a running seeded demo, the way an admin and an application would use it.

Standard library only. Run by scripts/smoke.sh after the stack is up; also runnable on its own:

    python3 scripts/smoke_quality.py            # against http://localhost:8000

It registers two models with the same capability, rates real answers through POST /v1/feedback, and checks that
`routing_quality_signal: feedback` lets feedback choose between them, but only among models authorized for the request.
It needs an empty model registry and restores the demo (signal off, routing off, registry and key removed).
Exits 1 if any outcome differs from what the signal should produce.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
ADMIN = (os.environ.get("ADMIN_EMAIL", "admin@example.com"), os.environ.get("ADMIN_PASSWORD", "DemoPass123!"))
CLIENT_KEY = os.environ.get("API_KEY", "opai_dev_demo0001_00000000000000000000000000demo01fea5")
CHEAP, STRONG = "openai/gpt-4o-mini", "openai/gpt-4o"
CAPABILITY = "cap:SUMMARIZATION"
RATINGS = 30  # per model; the signal ignores a model with fewer than 20

failures = 0


def call(method, path, *, token=None, body=None, headers=None):
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
    admin = call("POST", "/api/v1/auth/login", body={"email": ADMIN[0], "password": ADMIN[1]})[2]["access_token"]

    def policy(**fields):
        return call("PATCH", "/api/v1/organizations/current/policy", token=admin, body=fields)

    def chat(content, model, data_class=None):
        headers = {"x-openproxy-data-class": data_class} if data_class else {}
        return call("POST", "/v1/chat/completions", token=CLIENT_KEY, headers=headers,
                    body={"model": model, "messages": [{"role": "user", "content": content}]})

    def rate(request_id, thumbs):
        """Feedback needs the request's log row, which is written in the background: retry until it lands."""
        for _ in range(40):
            status, _, parsed = call("POST", "/v1/feedback", token=CLIENT_KEY, body={"request_id": request_id, "thumbs": thumbs})
            if status != 404:
                return status, parsed
            time.sleep(0.5)
        return 404, "the request log never landed"

    if call("GET", "/api/v1/model-registry", token=admin)[2]:
        sys.exit("The model registry is not empty. This script is for the seeded demo and needs an empty registry "
                 "(docker compose -f docker-compose.demo.yml down -v resets it).")
    created, key_id = [], None
    try:
        status, _, key = call("POST", "/api/v1/provider-keys", token=admin, body={
            "provider": "openai", "api_key": "sk-smoke-quality", "key_alias": "smoke-quality", "api_base": "http://fake-llm:9090/v1",
            "is_internal": True, "max_data_class": "confidential", "weight": 1})
        check("an internal endpoint key is accepted", status == 201, key)
        key_id = key.get("id")
        for model, data_class, cost in ((CHEAP, "internal", "low"), (STRONG, "confidential", "high")):
            status, _, body = call("POST", "/api/v1/model-registry", token=admin, body={
                "model_id": model, "provider_key_id": key_id, "max_data_class": data_class, "regions": ["us"],
                "capabilities": ["SUMMARIZATION"], "cost_tier": cost})
            check(f"register {model} ({data_class}, cost {cost})", status == 201, body)
            if status == 201:
                created.append(body["id"])
        check("enforce accepted", policy(routing_mode="enforce")[0] == 200)

        print("-- before any feedback: the cheapest authorized model, whatever the setting")
        status, headers, _ = chat(f"quality smoke baseline {os.urandom(4).hex()}", CAPABILITY)
        check("signal off: the cheaper model", status == 200 and headers.get("x-openproxyai-route-model") == CHEAP, headers)
        check("signal off: reason is capability", headers.get("x-openproxyai-route-reason") == "capability", headers)
        status, _, body = policy(routing_quality_signal="feedback")
        check("the setting is accepted and stored", status == 200 and body.get("routing_quality_signal") == "feedback", body)
        status, headers, _ = chat(f"quality smoke unrated {os.urandom(4).hex()}", CAPABILITY)
        check("signal on, nothing rated yet: still the cheaper model", headers.get("x-openproxyai-route-model") == CHEAP, headers)
        check("signal on, nothing rated yet: reason is capability", headers.get("x-openproxyai-route-reason") == "capability", headers)
        check("signal off again for the rating phase", policy(routing_quality_signal="off")[0] == 200)

        print(f"-- rate {RATINGS} real answers per model: the cheap one badly, the strong one well")
        problems = []
        for model, thumbs in ((CHEAP, "down"), (STRONG, "up")):
            for index in range(RATINGS):
                status, headers, body = chat(f"quality smoke {model} {index} {os.urandom(4).hex()}", model, data_class="internal")
                request_id = headers.get("x-openproxyai-request-id")
                if status != 200 or not request_id:
                    problems.append((model, index, "chat", status, str(body)[:120]))
                    continue
                rated, detail = rate(request_id, thumbs)
                if rated != 200:
                    problems.append((model, index, "rating", rated, str(detail)[:120]))
        check("every answer was served and its rating accepted", not problems, problems[:3])
        print("-- feedback decides, inside the authorized set")
        status, headers, _ = chat(f"quality smoke off {os.urandom(4).hex()}", CAPABILITY)
        check("signal off ignores the feedback: still the cheaper model", headers.get("x-openproxyai-route-model") == CHEAP, headers)
        check("signal on accepted", policy(routing_quality_signal="feedback")[0] == 200)
        # Feedback is read once a minute per org, and the "nothing rated yet" request above primed that read. Wait for it to refresh.
        for _ in range(16):
            status, headers, _ = chat(f"quality smoke on {os.urandom(4).hex()}", CAPABILITY)
            if headers.get("x-openproxyai-route-model") == STRONG:
                break
            time.sleep(5)
        check("signal on: the better-rated model serves (within the one-minute cache)", status == 200 and headers.get("x-openproxyai-route-model") == STRONG, headers)
        check("the reason says feedback decided", headers.get("x-openproxyai-route-reason") == "capability_quality", headers)

        status, _, preview = call("POST", "/api/v1/policy/preview", token=admin, body={
            "model": CAPABILITY, "messages": [{"role": "user", "content": "preview check"}]})
        check("the policy preview agrees", status == 200 and preview["routing"]["model"] == STRONG and preview["routing"]["reason"] == "capability_quality", preview)

        status, headers, _ = chat(f"quality smoke confidential {os.urandom(4).hex()}", CAPABILITY, data_class="confidential")
        check("confidential: the only cleared model (also the better rated)", status == 200 and headers.get("x-openproxyai-route-model") == STRONG, headers)
        status, _, body = chat(f"quality smoke secret {os.urandom(4).hex()}", CAPABILITY, data_class="secret")
        check("secret: nothing is cleared, so 446 however well a model is rated", status == 446 and body.get("route_reason") == "no_model_with_capability", body)
        status, headers, _ = chat(f"quality smoke exact {os.urandom(4).hex()}", CHEAP)
        check("an exact model request is never swapped for the better-rated one", status == 200 and headers.get("x-openproxyai-route-model") == CHEAP, headers)

        print("-- an excluded model stays excluded")
        # Rule the well-rated model out with the risk ceiling; the badly rated one is then the only authorized model.
        _, _, entry = call("GET", "/api/v1/model-registry", token=admin)
        strong_id = next(e["id"] for e in entry if e["model_id"] == STRONG)
        check("raise the strong model's risk rating", call("PATCH", f"/api/v1/model-registry/{strong_id}", token=admin, body={"risk_rating": "high"})[0] == 200)
        check("lower the risk ceiling", policy(max_risk_rating="medium")[0] == 200)
        status, headers, _ = chat(f"quality smoke risk {os.urandom(4).hex()}", CAPABILITY)
        check("the well-rated model is out (risk), so the cheap one serves", status == 200 and headers.get("x-openproxyai-route-model") == CHEAP, headers)
        check("and the reason is plain capability, not feedback", headers.get("x-openproxyai-route-reason") == "capability", headers)
        policy(max_risk_rating="high")
    finally:
        policy(routing_quality_signal="off")
        policy(routing_mode="off")
        for entry_id in created:
            call("DELETE", f"/api/v1/model-registry/{entry_id}", token=admin)
        if key_id:
            call("DELETE", f"/api/v1/provider-keys/{key_id}", token=admin)
        check("restored: routing off, the registry is empty again", call("GET", "/api/v1/model-registry", token=admin)[2] == [])

    if failures:
        print(f"{failures} quality-signal check(s) failed")
        sys.exit(1)
    print("quality signal smoke passed")


if __name__ == "__main__":
    main()
