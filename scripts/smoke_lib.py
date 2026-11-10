"""Shared helpers for the smoke scripts that run against the seeded demo stack. Standard library only."""

import json
import os
import subprocess
import urllib.error
import urllib.request

BASE = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
ADMIN = (os.environ.get("ADMIN_EMAIL", "admin@example.com"), os.environ.get("ADMIN_PASSWORD", "DemoPass123!"))
CLIENT_KEY = os.environ.get("API_KEY", "opai_dev_demo0001_00000000000000000000000000demo01fea5")
COMPOSE = ["docker", "compose", "-f", "docker-compose.demo.yml"]

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
    print(f"{'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"   [{str(detail)[:240]}]"))


def login_admin():
    status, _, tokens = call("POST", "/api/v1/auth/login", body={"email": ADMIN[0], "password": ADMIN[1]})
    return tokens["access_token"]


def sql(statement):
    """Rows of a query against the demo database, through `docker compose exec`, as lists of strings."""
    out = subprocess.run(
        [*COMPOSE, "exec", "-T", "postgres", "psql", "-U", "openproxyai", "-d", "openproxyai", "-tA", "-F", "|", "-c", statement],
        capture_output=True, text=True, check=True,
    ).stdout
    return [line.split("|") for line in out.splitlines() if line.strip()]
