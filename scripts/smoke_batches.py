#!/usr/bin/env python3
"""Checks files and batches on a running seeded demo: upload, run, output, policy per line, cap, cancel and isolation.

Standard library only. Run by scripts/smoke.sh; also runnable on its own (BASE_URL, FAKE_URL as in the other smoke scripts).
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

import smoke_lib
from smoke_lib import BASE, CLIENT_KEY, call, check, login_admin

FAKE_URL = os.environ.get("FAKE_URL", "http://localhost:9090").rstrip("/")


def line(custom_id, content, model="openai/gpt-4o-mini"):
    return json.dumps({"custom_id": custom_id, "method": "POST", "url": "/v1/chat/completions", "body": {"model": model, "messages": [{"role": "user", "content": content}]}})


def upload(lines, purpose="batch"):
    boundary = uuid.uuid4().hex
    data = ("\n".join(lines) + "\n").encode()
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="purpose"\r\n\r\n{purpose}\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="in.jsonl"\r\nContent-Type: application/jsonl\r\n\r\n').encode() + data + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(BASE + "/v1/files", data=body, method="POST", headers={"Authorization": f"Bearer {CLIENT_KEY}", "Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def wait(batch_id):
    for _ in range(120):
        _, _, job = call("GET", f"/v1/batches/{batch_id}", token=CLIENT_KEY)
        if job["status"] not in ("validating", "in_progress"):
            return job
        time.sleep(0.5)
    return job


def main():
    admin = login_admin()
    policy = lambda **fields: call("PATCH", "/api/v1/organizations/current/policy", token=admin, body=fields)  # noqa: E731
    try:
        print("-- upload")
        status, body = upload([line("a", "ok"), "{broken"])
        check("an invalid file is refused whole, naming the line (422)", status == 422 and "line 2" in body.get("detail", ""), body)
        unique = uuid.uuid4().hex[:8]
        status, file = upload([line("one", f"batch question one {unique}"), line("two", f"batch question two {unique}"), line("blocked", f"the falcon plan {unique}")])
        check("a valid file is stored", status == 200 and file["lines"] == 3 and file["purpose"] == "batch", (status, file))

        print("-- run, with policy applied to each line")
        check("a blocked keyword is set", policy(enforcement_mode="enforce", blocked_keywords=["falcon"])[0] == 200)
        status, _, started = call("POST", "/v1/batches", token=CLIENT_KEY, body={"input_file_id": file["id"], "max_cost_usd": 1})
        check("the batch starts", status == 200 and started["request_counts"]["total"] == 3, started)
        job = wait(started["id"])
        check("it completes", job["status"] == "completed" and job["request_counts"] == {"total": 3, "completed": 2, "failed": 1}, job)
        out = urllib.request.Request(BASE + f"/v1/files/{job['output_file_id']}/content", headers={"Authorization": f"Bearer {CLIENT_KEY}"})
        rows = {r["custom_id"]: r for r in map(json.loads, urllib.request.urlopen(out, timeout=30).read().decode().splitlines())}
        check("good lines are answered", rows["one"]["response"]["status_code"] == 200 and rows["one"]["response"]["body"]["choices"][0]["message"]["content"], rows.get("one"))
        check("the blocked line is refused (446) and only that line", rows["blocked"]["error"]["status_code"] == 446 and rows["two"]["error"] is None, rows.get("blocked"))
        calls = json.loads(urllib.request.urlopen(f"{FAKE_URL}/__calls", timeout=10).read())
        check("the provider never saw the blocked line", not any("the falcon plan " + unique in json.dumps(c.get("body", {})) for c in calls))
        policy(enforcement_mode="off", blocked_keywords=[])

        print("-- the spending cap and cancel")
        status, big = upload([line(f"l{i}", f"cap test {unique} {i}") for i in range(30)])
        status, _, started = call("POST", "/v1/batches", token=CLIENT_KEY, body={"input_file_id": big["id"], "max_cost_usd": 100})
        status, _, cancelled = call("POST", f"/v1/batches/{started['id']}/cancel", token=CLIENT_KEY)
        check("a running batch can be cancelled", status == 200 and cancelled["status"] == "cancelled", cancelled)
        check("an absurd cap is refused", call("POST", "/v1/batches", token=CLIENT_KEY, body={"input_file_id": big["id"], "max_cost_usd": 10**9})[0] == 422)
        wait(started["id"])

        print("-- cleanup")
        check("a file can be deleted", call("DELETE", f"/v1/files/{file['id']}", token=CLIENT_KEY)[0] == 200 and call("GET", f"/v1/files/{file['id']}", token=CLIENT_KEY)[0] == 404)
        call("DELETE", f"/v1/files/{big['id']}", token=CLIENT_KEY)
    finally:
        policy(enforcement_mode="off", blocked_keywords=[])

    if smoke_lib.failures:
        print(f"{smoke_lib.failures} batch check(s) failed")
        sys.exit(1)
    print("batches smoke passed")


if __name__ == "__main__":
    main()
