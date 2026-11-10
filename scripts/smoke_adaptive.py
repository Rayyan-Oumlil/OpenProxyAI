#!/usr/bin/env python3
"""Checks adaptive A/B experiments on a running seeded demo: real traffic is split, feedback is linked to the variant that
served it, and the real periodic job moves traffic and stops the test with a winner.

Standard library only. Run by scripts/smoke.sh after the stack is up; also runnable on its own:

    python3 scripts/smoke_adaptive.py            # against http://localhost:8000

A handful of real requests prove the split and the linkage. The volume of feedback a decision needs (the minimum is 20
per variant) is inserted directly, because pushing 50 real requests would only hit the 60 requests/minute default limit.
The job is run inside the API container, as the scheduler would. Removes what it created. Exits 1 on any difference.
"""

import subprocess
import sys
import time

import smoke_lib as lib
from smoke_lib import CLIENT_KEY, COMPOSE, call, check, login_admin, sql

TARGET = "openai/gpt-4o"
WEAK, STRONG = "openai/gpt-4o-mini", "openai/gpt-4o"


def chat():
    status, headers, _ = call("POST", "/v1/chat/completions", token=CLIENT_KEY,
                              body={"model": TARGET, "messages": [{"role": "user", "content": f"adaptive smoke {time.time()}"}]})
    return status, headers.get("x-openproxyai-request-id", "")


def rate(request_id, thumbs):
    for _ in range(40):  # the request log is written just after the response
        status, _, _ = call("POST", "/v1/feedback", token=CLIENT_KEY, body={"request_id": request_id, "thumbs": thumbs})
        if status != 404:
            return status
        time.sleep(0.5)
    return status


def run_the_job():
    out = subprocess.run(
        [*COMPOSE, "exec", "-T", "api", "python", "-c",
         "import asyncio; from app.services.adaptive_experiments import update_adaptive_experiments; print('LOOKED', asyncio.run(update_adaptive_experiments()))"],
        capture_output=True, text=True,
    )
    return out.stdout


def seed(experiment_id, variant_id, total, up):
    sql(
        "INSERT INTO request_scores (request_id, org_id, experiment_id, variant_id, score_name, value) "
        f"SELECT gen_random_uuid(), e.org_id, e.id, '{variant_id}', 'thumbs', CASE WHEN g <= {up} THEN 1 ELSE 0 END "
        f"FROM experiments e, generate_series(1, {total}) g WHERE e.id = '{experiment_id}'"
    )


def main():
    admin = login_admin()
    stamp = int(time.time())
    experiment_id = None
    try:
        status, _, created = call("POST", "/api/v1/experiments", token=admin, body={
            "name": f"adaptive-smoke-{stamp}", "target_model": TARGET, "mode": "adaptive", "metric": "thumbs",
            "min_samples_per_variant": 20, "variants": [{"model": WEAK, "traffic_weight": 50}, {"model": STRONG, "traffic_weight": 50}],
        })
        experiment_id = created.get("id") if status in (200, 201) else None
        check("an adaptive experiment is created with the safe defaults",
              status in (200, 201) and (created["mode"], created["metric"], created["delta"], created["weight_floor"]) == ("adaptive", "thumbs", 0.01, 5), (status, created))
        if not experiment_id:
            raise SystemExit("cannot continue without an experiment")
        weak_id, strong_id = created["variants"][0]["id"], created["variants"][1]["id"]

        status, _, bad = call("POST", "/api/v1/experiments", token=admin, body={
            "name": "bad", "target_model": "openai/gpt-4o-mini", "mode": "adaptive", "variants": [{"model": WEAK, "traffic_weight": 100}]})
        check("an adaptive experiment with no metric and one variant is refused (422)", status == 422 and bad["detail"]["error"] == "invalid_adaptive_experiment", (status, bad))

        request_ids = []
        for _ in range(10):
            status, request_id = chat()
            if status == 200:
                request_ids.append(request_id)
        check("ten real requests to the target model were served", len(request_ids) == 10, len(request_ids))
        assigned = sql("SELECT request_metadata->'experiment'->>'variant_id', count(*) FROM request_logs "
                       f"WHERE request_metadata->'experiment'->>'experiment_id' = '{experiment_id}' GROUP BY 1")
        for _ in range(20):
            if sum(int(n) for _, n in assigned) >= 10:
                break
            time.sleep(0.5)
            assigned = sql("SELECT request_metadata->'experiment'->>'variant_id', count(*) FROM request_logs "
                           f"WHERE request_metadata->'experiment'->>'experiment_id' = '{experiment_id}' GROUP BY 1")
        check("each real request was assigned to one of the two variants and logged with its id",
              sum(int(n) for _, n in assigned) == 10 and {v for v, _ in assigned} <= {weak_id, strong_id}, assigned)

        check("real feedback was accepted for each of them", all(rate(r, "up") == 200 for r in request_ids))
        linked = sql(f"SELECT count(*), count(variant_id) FROM request_scores WHERE experiment_id = '{experiment_id}'")
        check("each rating is stored against the experiment and the variant that served it", linked == [["10", "10"]], linked)

        # Not enough data yet: the real job must change nothing.
        before = run_the_job()
        _, _, early = call("GET", f"/api/v1/experiments/{experiment_id}", token=admin)
        check("with too little feedback the job changes nothing (still active, weights 50/50)",
              "LOOKED" in before and early["is_active"] and [v["traffic_weight"] for v in early["variants"]] == [50, 50] and early["winner_variant_id"] is None, (before, early))

        # Enough data, and the stronger variant is clearly better.
        seed(experiment_id, weak_id, 30, 6)
        seed(experiment_id, strong_id, 30, 26)
        after = run_the_job()
        status, _, done = call("GET", f"/api/v1/experiments/{experiment_id}", token=admin)
        check("the job named the stronger variant the winner and stopped the test",
              "LOOKED" in after and status == 200 and not done["is_active"] and done["stopped_reason"] == "winner" and done["winner_variant_id"] == strong_id, (after, done))
        check("the target model that production traffic goes to is unchanged", done["target_model"] == TARGET, done)

        status, _, results = call("GET", f"/api/v1/experiments/{experiment_id}/results", token=admin)
        adaptive = results.get("adaptive") or {}
        check("the results report the two variants separately with the chance each is best",
              status == 200 and adaptive.get("ready") is True and adaptive.get("winner_variant_id") == strong_id
              and {v["variant_id"] for v in results["variants"]} <= {weak_id, strong_id}, (status, results))
        best = {v["variant_id"]: v["probability_best"] for v in results["variants"]}
        check("the stronger variant is shown as almost certainly best", best.get(strong_id, 0) > 0.99, best)

        check("the winner was recorded in the admin audit log by the system actor",
              sql(f"SELECT actor_email FROM admin_audit_logs WHERE resource_id = '{experiment_id}' AND action = 'experiment.winner_found'") == [["system:adaptive-ab"]])

        # After the stop the split is over: a request to the target model is no longer assigned a variant.
        status, request_id = chat()
        time.sleep(2)
        tagged = sql(f"SELECT request_metadata->'experiment' IS NOT NULL FROM request_logs WHERE request_id = '{request_id}'")
        check("after the stop, requests go to the target model with no variant assigned", status == 200 and tagged == [["f"]], (status, tagged))

        status, _, restarted = call("POST", f"/api/v1/experiments/{experiment_id}/start", token=admin)
        check("starting it again clears the winner", status == 200 and restarted["is_active"] and restarted["winner_variant_id"] is None and restarted["stopped_reason"] is None, (status, restarted))
    finally:
        if experiment_id:
            call("DELETE", f"/api/v1/experiments/{experiment_id}", token=admin)

    if lib.failures:
        print(f"{lib.failures} adaptive check(s) failed")
        sys.exit(1)
    print("adaptive smoke passed")


if __name__ == "__main__":
    main()
