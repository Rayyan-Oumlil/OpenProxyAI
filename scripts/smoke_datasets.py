#!/usr/bin/env python3
"""Checks the eval loop's data path on a running seeded demo, as an admin and an application would use it:

    capture (opt-in) -> feedback -> dataset -> import (with filters) -> items -> delete

Standard library only. Run by scripts/smoke.sh after the stack is up; also runnable on its own:

    python3 scripts/smoke_datasets.py            # against http://localhost:8000

Uses the real login (no test overrides) and the real database. Restores the demo's policy and removes what it
created when it finishes. Exits 1 on any difference.
"""

import sys
import time
from datetime import UTC, datetime, timedelta

import smoke_lib as lib
from smoke_lib import CLIENT_KEY, call, check, login_admin, sql


def chat(content):
    status, headers, _ = call(
        "POST", "/v1/chat/completions", token=CLIENT_KEY,
        body={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": content}]},
    )
    return status, headers.get("x-openproxyai-request-id", "")


def wait_for_payload(request_id):
    for _ in range(30):
        if sql(f"SELECT 1 FROM request_payloads WHERE request_id = '{request_id}'"):
            return True
        time.sleep(0.5)
    return False


def rate(request_id, thumbs):
    for _ in range(40):  # the request log is written just after the response
        status, _, parsed = call("POST", "/v1/feedback", token=CLIENT_KEY, body={"request_id": request_id, "thumbs": thumbs})
        if status != 404:
            return status
        time.sleep(0.5)
    return status


def main():
    admin = login_admin()
    started = (datetime.now(UTC) - timedelta(seconds=5)).isoformat()  # earlier captures in this database are not mine
    stamp = int(time.time())
    _, _, original = call("GET", "/api/v1/organizations/current/policy", token=admin)
    dataset_id = None

    try:
        call("PATCH", "/api/v1/organizations/current/policy", token=admin, body={"payload_capture_sample_rate": 1, "enforcement_mode": "log_only"})
        status_a, rid_rated = chat(f"dataset smoke rated {stamp}")
        status_b, rid_unrated = chat(f"dataset smoke unrated {stamp}")
        status_c, rid_pii = chat(f"dataset smoke {stamp}, mail jane.doe@example.com")
        check("three requests were sent and captured", status_a == status_b == status_c == 200 and all(wait_for_payload(r) for r in (rid_rated, rid_unrated, rid_pii)))
        check("the request with an email address was captured redacted", sql(f"SELECT redacted::text FROM request_payloads WHERE request_id = '{rid_pii}'") == [["true"]])
        check("one answer was rated thumbs up with the API key", rate(rid_rated, "up") == 200)

        status, _, created = call("POST", "/api/v1/datasets", token=admin, body={"name": f"smoke-{stamp}", "description": "created by the smoke test"})
        dataset_id = created.get("id") if status == 201 else None
        check("an admin creates a dataset (201)", status == 201 and created["item_count"] == 0, (status, created))
        if not dataset_id:
            raise SystemExit("cannot continue without a dataset")
        status, _, again = call("POST", "/api/v1/datasets", token=admin, body={"name": f"smoke-{stamp}"})
        check("the same name again is a 409", status == 409, (status, again))

        status, _, first = call("POST", f"/api/v1/datasets/{dataset_id}/import", token=admin, body={"since": started, "score_name": "thumbs", "min_score": 1})
        check("importing only thumbs-up answers copies exactly the rated one", status == 200 and first["imported"] == 1, (status, first))

        status, _, second = call("POST", f"/api/v1/datasets/{dataset_id}/import", token=admin, body={"since": started})
        check("importing everything adds the unrated one, skips the repeat, and refuses the one with PII",
              status == 200 and (second["imported"], second["skipped_duplicate"], second["skipped_redacted"]) == (1, 1, 1), (status, second))

        status, _, items = call("GET", f"/api/v1/datasets/{dataset_id}/items", token=admin)
        texts = " ".join(str(i["messages"]) for i in items) if status == 200 else ""
        check("the dataset holds the two clean prompts and no email address",
              status == 200 and len(items) == 2 and f"rated {stamp}" in texts and f"unrated {stamp}" in texts and "jane.doe" not in texts, (status, texts[:200]))

        status, _, refused = call("POST", f"/api/v1/datasets/{dataset_id}/items", token=admin, body={"messages": [{"role": "user", "content": "my SSN is 123-45-6789"}]})
        check("an item with an SSN is refused (422, pii_in_item)", status == 422 and refused["detail"]["error"] == "pii_in_item", (status, refused))
        status, _, added = call("POST", f"/api/v1/datasets/{dataset_id}/items", token=admin, body={"messages": [{"role": "user", "content": "What is 2+2?"}], "expected": "4"})
        check("a hand-written item with an expected answer is accepted", status == 201 and added["expected"] == "4", (status, added))
        status, _, got = call("GET", f"/api/v1/datasets/{dataset_id}", token=admin)
        check("the dataset now counts three items", status == 200 and got["item_count"] == 3, (status, got))

        status, _, _ = call("POST", "/api/v1/datasets", token=CLIENT_KEY, body={"name": "nope"})
        check("an API key is not an admin login (datasets refuse it)", status in (401, 403), status)

        status, _, _ = call("DELETE", f"/api/v1/datasets/{dataset_id}", token=admin)
        check("deleting the dataset is a 204", status == 204, status)
        check("its items are gone with it", sql(f"SELECT count(*) FROM dataset_items WHERE dataset_id = '{dataset_id}'") == [["0"]])
        dataset_id = None
        check("the admin audit log recorded creating, importing and deleting",
              {r[0] for r in sql(f"SELECT action FROM admin_audit_logs WHERE resource_type = 'dataset' AND after->>'name' = 'smoke-{stamp}'")} == {"dataset.created", "dataset.imported", "dataset.deleted"})
    finally:
        if dataset_id:
            call("DELETE", f"/api/v1/datasets/{dataset_id}", token=admin)
        restore = {k: original[k] for k in ("payload_capture_sample_rate", "enforcement_mode") if k in original}
        call("PATCH", "/api/v1/organizations/current/policy", token=admin, body=restore)
        sql("DELETE FROM request_payloads")

    if lib.failures:
        print(f"{lib.failures} dataset check(s) failed")
        sys.exit(1)
    print("datasets smoke passed")


if __name__ == "__main__":
    main()
