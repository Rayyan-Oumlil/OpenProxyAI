#!/usr/bin/env python3
"""Checks the prompt promotion gate on a running seeded demo, with the real login and the real eval-run executor:

    live prompt -> gate on -> edit makes a draft -> refused without a run -> run of the draft -> promoted -> override -> stale run

Standard library only. Run by scripts/smoke.sh after the stack is up; also runnable on its own:

    python3 scripts/smoke_promotion.py            # against http://localhost:8000

Clients call a prompt by prompt_id, so "live" is observable the way a client sees it: a draft or retired version answers
prompt_not_found. Restores the demo's policy and removes what it created. Exits 1 on any difference.
"""

import sys
import time

import smoke_lib as lib
from smoke_lib import CLIENT_KEY, call, check, login_admin, sql

TERMINAL = {"completed", "failed", "cancelled", "budget_exceeded"}
TEMPLATES = "/api/v1/prompt-templates"


def use(prompt_id):
    """What a client sees when it calls a prompt by id."""
    status, _, body = call("POST", "/v1/chat/completions", token=CLIENT_KEY,
                           body={"model": "openai/gpt-4o-mini", "prompt_id": prompt_id, "variables": {"q": "hello"}})
    return status, body


def wait_done(run_id, admin):
    for _ in range(120):
        _, _, run = call("GET", f"/api/v1/eval-runs/{run_id}", token=admin)
        if run["status"] in TERMINAL:
            return run
        time.sleep(0.5)
    return run


def main():
    admin = login_admin()
    stamp = int(time.time())
    name = f"promo-smoke-{stamp}"
    _, _, original = call("GET", "/api/v1/organizations/current/policy", token=admin)
    made = {"datasets": [], "evaluators": []}

    def policy(**fields):
        status, _, body = call("PATCH", "/api/v1/organizations/current/policy", token=admin, body=fields)
        assert status == 200, (status, body)

    try:
        status, _, live = call("POST", TEMPLATES, token=admin, body={"name": name, "system_message": "You are a concise assistant.", "user_template": "{{q}}"})
        check("with the gate off a new prompt is live straight away", status == 201 and live["status"] == "active" and use(live["id"])[0] == 200, (status, live))

        policy(prompt_promotion_gate=True, prompt_gate_min_items=3, prompt_gate_min_pass_rate=0.8)
        status, _, draft = call("PUT", f"{TEMPLATES}/{live['id']}", token=admin, body={"system_message": "You are a very concise assistant."})
        check("with the gate on an edit makes a draft (v2)", status == 200 and (draft["status"], draft["version"], draft["is_active"]) == ("draft", 2, False), (status, draft))
        check("the old version keeps serving while the draft is not usable",
              use(live["id"])[0] == 200 and use(draft["id"])[0] == 404 and use(draft["id"])[1].get("error") == "prompt_not_found", (use(live["id"]), use(draft["id"])))

        status, _, again = call("PUT", f"{TEMPLATES}/{live['id']}", token=admin, body={"user_template": "other"})
        check("a second draft of the same prompt is refused (409)", status == 409 and again["detail"]["error"] == "draft_exists", (status, again))

        status, _, refused = call("POST", f"{TEMPLATES}/{draft['id']}/promote", token=admin, body={})
        check("promoting with no eval run is refused and says why", status == 409 and refused["detail"]["error"] == "promotion_gate_failed"
              and "no eval run has tested this exact prompt" in refused["detail"]["reasons"][0], (status, refused))

        # Test the draft with a real run.
        status, _, ds = call("POST", "/api/v1/datasets", token=admin, body={"name": f"{name}-ds"})
        made["datasets"].append(ds["id"])
        for i in range(4):
            call("POST", f"/api/v1/datasets/{ds['id']}/items", token=admin, body={"messages": [{"role": "user", "content": f"promo question {i} {stamp}"}]})
        _, _, ev = call("POST", "/api/v1/evaluators", token=admin, body={"name": f"{name}-ev", "type": "regex", "config": {"pattern": "^echo: "}})
        made["evaluators"].append(ev["id"])
        status, _, run = call("POST", "/api/v1/eval-runs", token=admin, body={
            "dataset_id": ds["id"], "evaluator_id": ev["id"], "candidate_model": "openai/gpt-4o-mini", "prompt_template_id": draft["id"]})
        done = wait_done(run["id"], admin)
        check("a run of the draft completed and every item passed", status == 202 and (done["status"], done["scored_items"], done["pass_rate"]) == ("completed", 4, 1.0), (status, done))

        status, _, view = call("GET", f"{TEMPLATES}/{draft['id']}/promotion", token=admin)
        check("the promotion status now says the gate is satisfied, by that run",
              status == 200 and view["passes_gate"] and view["qualifying_run"]["run_id"] == run["id"] and view["reasons"] == [], (status, view))

        status, _, promoted = call("POST", f"{TEMPLATES}/{draft['id']}/promote", token=admin, body={})
        check("the draft is promoted, replacing v1", status == 200 and (promoted["version"], promoted["previous_version"], promoted["overridden"], promoted["run_id"]) == (2, 1, False, run["id"]), (status, promoted))
        check("clients now get the new version, and the old one is retired", use(draft["id"])[0] == 200 and use(live["id"])[0] == 404, (use(draft["id"]), use(live["id"])))

        # Override.
        status, _, v3 = call("PUT", f"{TEMPLATES}/{draft['id']}", token=admin, body={"system_message": "An urgent fix."})
        status, _, no_reason = call("POST", f"{TEMPLATES}/{v3['id']}/promote", token=admin, body={"override": True})
        check("an override without a reason is refused (422)", status == 422 and no_reason["detail"]["error"] == "override_needs_reason", (status, no_reason))
        status, _, forced = call("POST", f"{TEMPLATES}/{v3['id']}/promote", token=admin, body={"override": True, "reason": "Urgent customer-facing fix, run to follow"})
        check("an override with a reason promotes and is marked as one", status == 200 and forced["overridden"] is True and forced["version"] == 3, (status, forced))
        check("the override and its reason are in the admin audit log",
              sql(f"SELECT after->>'override_reason' FROM admin_audit_logs WHERE action = 'prompt_template.promoted_with_override' AND resource_id = '{v3['id']}'")
              == [["Urgent customer-facing fix, run to follow"]])

        # A run stops counting once the draft is edited.
        status, _, v4 = call("PUT", f"{TEMPLATES}/{v3['id']}", token=admin, body={"system_message": "Version four."})
        _, _, run4 = call("POST", "/api/v1/eval-runs", token=admin, body={
            "dataset_id": ds["id"], "evaluator_id": ev["id"], "candidate_model": "openai/gpt-4o-mini", "prompt_template_id": v4["id"]})
        wait_done(run4["id"], admin)
        call("PUT", f"{TEMPLATES}/{v4['id']}", token=admin, body={"system_message": "Version four, edited after its run."})
        status, _, stale = call("POST", f"{TEMPLATES}/{v4['id']}/promote", token=admin, body={})
        check("editing a draft after its run means the run no longer counts", status == 409 and "no eval run has tested this exact prompt" in stale["detail"]["reasons"][0], (status, stale))

        status, _, nobody = call("POST", f"{TEMPLATES}/{v4['id']}/promote", token=CLIENT_KEY, body={})
        check("an API key is not an admin login (promotion refuses it)", status in (401, 403), status)
    finally:
        for dataset_id in made["datasets"]:
            call("DELETE", f"/api/v1/datasets/{dataset_id}", token=admin)
        for evaluator_id in made["evaluators"]:
            call("DELETE", f"/api/v1/evaluators/{evaluator_id}", token=admin)
        sql(f"DELETE FROM eval_runs WHERE prompt_template_id IN (SELECT id FROM prompt_templates WHERE name = '{name}')")
        sql(f"DELETE FROM prompt_templates WHERE name = '{name}'")
        restore = {k: original[k] for k in ("prompt_promotion_gate", "prompt_gate_min_items", "prompt_gate_min_pass_rate") if k in original}
        call("PATCH", "/api/v1/organizations/current/policy", token=admin, body=restore)

    if lib.failures:
        print(f"{lib.failures} promotion check(s) failed")
        sys.exit(1)
    print("promotion smoke passed")


if __name__ == "__main__":
    main()
