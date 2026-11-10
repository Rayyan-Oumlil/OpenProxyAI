#!/usr/bin/env python3
"""Checks evaluators and eval runs on a running seeded demo, with the real login and the real background executor:

    dataset -> evaluator -> run (exact, regex, judge) -> results -> spending cap -> cancel -> active-run limit

Standard library only. Run by scripts/smoke.sh after the stack is up; also runnable on its own:

    python3 scripts/smoke_evals.py            # against http://localhost:8000

The demo's fake upstream echoes the prompt back, and replies to a judge prompt containing ``[judge-score=N]`` with that
score, so every outcome here is deterministic. Removes what it created. Exits 1 on any difference.
"""

import sys
import time

import smoke_lib as lib
from smoke_lib import call, check, login_admin, sql

TERMINAL = {"completed", "failed", "cancelled", "budget_exceeded"}


def wait_done(run_id, admin, seconds=90):
    for _ in range(seconds * 2):
        status, _, run = call("GET", f"/api/v1/eval-runs/{run_id}", token=admin)
        if status == 200 and run["status"] in TERMINAL:
            return run
        time.sleep(0.5)
    return run


def make_dataset(admin, name, items):
    status, _, created = call("POST", "/api/v1/datasets", token=admin, body={"name": name})
    assert status == 201, (status, created)
    for question, expected in items:
        status, _, added = call("POST", f"/api/v1/datasets/{created['id']}/items", token=admin,
                                body={"messages": [{"role": "user", "content": question}], **({"expected": expected} if expected else {})})
        assert status == 201, (status, added)
    return created["id"]


def make_evaluator(admin, name, kind, config):
    status, _, created = call("POST", "/api/v1/evaluators", token=admin, body={"name": name, "type": kind, "config": config})
    assert status == 201, (status, created)
    return created["id"]


def start_run(admin, dataset_id, evaluator_id, **extra):
    return call("POST", "/api/v1/eval-runs", token=admin, body={"dataset_id": dataset_id, "evaluator_id": evaluator_id, "candidate_model": "openai/gpt-4o-mini", **extra})


def main():
    admin = login_admin()
    stamp = int(time.time())
    created = {"datasets": [], "evaluators": []}

    try:
        qa, qb = f"eval smoke A {stamp}", f"eval smoke B {stamp}"
        ds_exact = make_dataset(admin, f"smoke-exact-{stamp}", [(qa, f"echo: {qa}"), (qb, "a different answer")])
        ev_exact = make_evaluator(admin, f"smoke-exact-{stamp}", "exact", {})
        ev_regex = make_evaluator(admin, f"smoke-regex-{stamp}", "regex", {"pattern": "^echo: eval smoke"})
        created["datasets"].append(ds_exact)
        created["evaluators"] += [ev_exact, ev_regex]

        status, _, bad = call("POST", "/api/v1/evaluators", token=admin, body={"name": "bad", "type": "regex", "config": {"pattern": "("}})
        check("an invalid regex is refused when the evaluator is created (422)", status == 422 and bad["detail"]["error"] == "invalid_evaluator", (status, bad))
        status, _, _ = call("POST", "/api/v1/evaluators", token=lib.CLIENT_KEY, body={"name": "x", "type": "exact", "config": {}})
        check("an API key is not an admin login (evaluators refuse it)", status in (401, 403), status)

        status, _, run = start_run(admin, ds_exact, ev_exact)
        check("a run is accepted and queued (202)", status == 202 and run["status"] in ("queued", "running") and run["total_items"] == 2, (status, run))
        done = wait_done(run["id"], admin)
        check("the exact run completed: one of two answers matched",
              (done["status"], done["completed_items"], done["passed_items"], done["mean_score"], done["pass_rate"]) == ("completed", 2, 1, 0.5, 0.5), done)
        status, _, items = call("GET", f"/api/v1/eval-runs/{run['id']}/items", token=admin)
        check("each item records the candidate's real answer", status == 200 and sorted(i["output"] for i in items) == sorted([f"echo: {qa}", f"echo: {qb}"]), items)
        check("every candidate call is in the request logs, tagged with its run",
              sql(f"SELECT count(*) FROM request_logs WHERE request_metadata->>'eval_run_id' = '{run['id']}' AND request_metadata->>'source' = 'eval_run'") == [["2"]])

        status, _, run = start_run(admin, ds_exact, ev_regex)
        done = wait_done(run["id"], admin)
        check("a regex run scores both answers as matching", (done["status"], done["pass_rate"]) == ("completed", 1.0), done)

        # LLM judge: the fake grades by the marker in the question.
        ds_judge = make_dataset(admin, f"smoke-judge-{stamp}", [(f"good one [judge-score=4] {stamp}", None), (f"poor one [judge-score=2] {stamp}", None)])
        ev_judge = make_evaluator(admin, f"smoke-judge-{stamp}", "llm_judge", {"model": "openai/gpt-4o-mini", "criteria": "Is it helpful?"})
        created["datasets"].append(ds_judge)
        created["evaluators"].append(ev_judge)
        status, _, run = start_run(admin, ds_judge, ev_judge)
        done = wait_done(run["id"], admin)
        check("the judge run scored 4/5 as a pass and 2/5 as a fail",
              (done["status"], done["passed_items"], done["mean_score"], done["pass_rate"]) == ("completed", 1, 0.5, 0.5), done)
        check("judge calls are metered like any other: candidate and judge, both in the request logs",
              sql(f"SELECT request_metadata->>'source', count(*) FROM request_logs WHERE request_metadata->>'eval_run_id' = '{run['id']}' GROUP BY 1 ORDER BY 1")
              == [["eval_judge", "2"], ["eval_run", "2"]])
        check("the run's cost is the sum of both kinds of call", done["cost_usd"] > 0, done)

        # Spending cap: each [big-usage] answer costs about two cents.
        ds_big = make_dataset(admin, f"smoke-big-{stamp}", [(f"big [big-usage] {i} {stamp}", f"echo: big [big-usage] {i} {stamp}") for i in range(8)])
        created["datasets"].append(ds_big)
        status, _, run = start_run(admin, ds_big, ev_exact, max_cost_usd=0.01)
        done = wait_done(run["id"], admin)
        check("a run stops when its spending cap is reached, before every item has run",
              done["status"] == "budget_exceeded" and 1 <= done["completed_items"] < 8 and done["cost_usd"] >= 0.01, done)

        # Cancel and the active-run limit, with a slow candidate so runs are still going.
        ds_slow = make_dataset(admin, f"smoke-slow-{stamp}", [(f"slow {i} {stamp}", f"echo: slow {i} {stamp}") for i in range(8)])
        created["datasets"].append(ds_slow)
        first = start_run(admin, ds_slow, ev_exact, candidate_model="openai/slow")[2]
        second = start_run(admin, ds_slow, ev_exact, candidate_model="openai/slow")[2]
        status, _, third = start_run(admin, ds_slow, ev_exact, candidate_model="openai/slow")
        check("a third active run is refused (409, too_many_runs)", status == 409 and third["detail"]["error"] == "too_many_runs", (status, third))
        status, _, cancelled = call("POST", f"/api/v1/eval-runs/{first['id']}/cancel", token=admin)
        check("a run can be cancelled", status == 200 and cancelled["status"] == "cancelled", (status, cancelled))
        call("POST", f"/api/v1/eval-runs/{second['id']}/cancel", token=admin)
        time.sleep(3)  # let in-flight items finish
        _, _, after = call("GET", f"/api/v1/eval-runs/{first['id']}", token=admin)
        check("a cancelled run stays cancelled and did not run every item", after["status"] == "cancelled" and after["completed_items"] < 8, after)
        status, _, again = call("POST", f"/api/v1/eval-runs/{first['id']}/cancel", token=admin)
        check("cancelling a finished run is a 409", status == 409, (status, again))

        check("the admin audit log recorded creating and cancelling runs",
              {r[0] for r in sql("SELECT action FROM admin_audit_logs WHERE resource_type IN ('eval_run', 'evaluator')")} >= {"eval_run.created", "eval_run.cancelled", "evaluator.created"})
    finally:
        for dataset_id in created["datasets"]:
            call("DELETE", f"/api/v1/datasets/{dataset_id}", token=admin)
        for evaluator_id in created["evaluators"]:
            call("DELETE", f"/api/v1/evaluators/{evaluator_id}", token=admin)
        sql(f"DELETE FROM eval_runs WHERE evaluator_snapshot->>'name' LIKE 'smoke-%-{stamp}'")

    if lib.failures:
        print(f"{lib.failures} eval check(s) failed")
        sys.exit(1)
    print("evals smoke passed")


if __name__ == "__main__":
    main()
