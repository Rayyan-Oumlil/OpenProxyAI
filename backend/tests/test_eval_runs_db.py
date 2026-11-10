"""Evaluators and eval runs against the real schema: the admin API, the executor, spending cap, cancel and sweeper (slice 4).

The only things replaced are the model calls (``run_prompt``), so everything else is the real code on real Postgres.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text

from app.database import SystemSessionLocal, org_scoped_session
from app.models.admin_audit_log import AdminAuditLog
from app.models.evaluation import EvalRun
from app.models.prompt_template import PromptTemplate
from app.services import eval_runner, evaluators
from app.services.model_runner import RunOutcome
from tests.db_helpers import Api, make_user
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)

DATASETS, EVALUATORS, RUNS = "/api/v1/datasets", "/api/v1/evaluators", "/api/v1/eval-runs"
EXACT = {"name": "exact-match", "type": "exact", "config": {}}
JUDGE = {"name": "quality-judge", "type": "llm_judge", "config": {"model": "openai/gpt-4o", "criteria": "Is it correct?"}}


@pytest.fixture
def models(monkeypatch):
	"""Scripted model calls. ``answers`` maps a prompt to the candidate's reply; ``seen`` records what was sent."""
	state = SimpleNamespace(answers={}, calls=[], judge_calls=[], cost=Decimal("0.1"), judge_score=5, judge_cost=Decimal("0.05"), on_call=None)

	async def candidate(**kwargs):
		state.calls.append(kwargs)
		if state.on_call:
			await state.on_call(len(state.calls))
		question = kwargs["messages"][-1]["content"]
		reply = state.answers.get(question, f"answer to {question}")
		return reply if isinstance(reply, RunOutcome) else RunOutcome(content=reply, cost_usd=state.cost, latency_ms=12)

	async def judge(**kwargs):
		state.judge_calls.append(kwargs)
		return RunOutcome(content=f'{{"score": {state.judge_score}, "reason": "graded"}}', cost_usd=state.judge_cost)

	monkeypatch.setattr(eval_runner, "run_prompt", candidate)
	monkeypatch.setattr(evaluators, "run_prompt", judge)
	monkeypatch.setattr(eval_runner, "CONCURRENCY", 1)  # one at a time keeps cancel and budget tests deterministic
	return state


@pytest.fixture
def started(monkeypatch):
	"""Creating a run normally starts it in the background; tests start it themselves, so record instead."""
	launched = []
	monkeypatch.setattr(eval_runner, "start", lambda run_id, org_id, user_id, redis: launched.append((run_id, org_id, user_id, redis)))
	return launched


async def make_dataset(api, items, name="regression") -> str:
	created = await api.http.post(DATASETS, json={"name": name})
	assert created.status_code == 201, created.text
	dataset_id = created.json()["id"]
	for question, expected in items:
		added = await api.http.post(f"{DATASETS}/{dataset_id}/items", json={"messages": [{"role": "user", "content": question}], "expected": expected})
		assert added.status_code == 201, added.text
	return dataset_id


async def make_evaluator(api, body=EXACT) -> str:
	created = await api.http.post(EVALUATORS, json=body)
	assert created.status_code == 201, created.text
	return created.json()["id"]


async def start_run(api, dataset_id, evaluator_id, **overrides):
	body = {"dataset_id": dataset_id, "evaluator_id": evaluator_id, "candidate_model": "openai/gpt-4o-mini", **overrides}
	return await api.http.post(RUNS, json=body)


async def run_to_the_end(api, started, user, **overrides) -> dict:
	"""Create a run with the usual fixtures, execute it in the foreground, and return its final state."""
	created = await start_run(api, overrides.pop("dataset_id"), overrides.pop("evaluator_id"), **overrides)
	assert created.status_code == 202, created.text
	run_id = created.json()["id"]
	[(rid, org_id, user_id, redis)] = started[-1:]
	await eval_runner.execute_run(rid, org_id, user_id, redis)
	return (await api.http.get(f"{RUNS}/{run_id}")).json()


# -- evaluators API -----------------------------------------------------------------------------------


async def test_each_kind_of_evaluator_can_be_created_and_gets_its_defaults_filled_in(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		made = {
			body["type"]: (await api.http.post(EVALUATORS, json=body)).json()
			for body in (EXACT, {"name": "digits", "type": "regex", "config": {"pattern": r"^\d+$"}}, JUDGE)
		}
		assert made["exact"]["config"] == {"case_sensitive": False, "strip": True}
		assert made["regex"]["config"]["mode"] == "search" and made["llm_judge"]["config"]["pass_threshold"] == 4
		assert [e["name"] for e in (await api.http.get(EVALUATORS)).json()] == ["digits", "exact-match", "quality-judge"]
		assert (await api.http.get(f"{EVALUATORS}/{made['exact']['id']}")).json()["type"] == "exact"


@pytest.mark.parametrize(
	"body,message",
	[
		({"name": "x", "type": "regex", "config": {}}, "pattern"),
		({"name": "x", "type": "regex", "config": {"pattern": "("}}, "valid"),
		({"name": "x", "type": "llm_judge", "config": {"model": "gpt-4o", "criteria": "c"}}, "provider/model"),
		({"name": "x", "type": "exact", "config": {"typo": True}}, "unknown"),
	],
)
async def test_a_bad_evaluator_config_is_a_422_that_says_what_is_wrong(tenants, body, message):
	async with Api(tenants.a, tenants.user_a) as api:
		refused = await api.http.post(EVALUATORS, json=body)
		assert refused.status_code == 422 and refused.json()["detail"]["error"] == "invalid_evaluator" and message in refused.json()["detail"]["detail"]


async def test_evaluator_names_are_unique_per_org_and_orgs_cannot_see_each_other(tenants):
	user_b = await make_user(tenants.b)
	async with Api(tenants.a, tenants.user_a) as api:
		evaluator_id = await make_evaluator(api)
		assert (await api.http.post(EVALUATORS, json=EXACT)).status_code == 409
	async with Api(tenants.b, user_b) as api:
		assert (await api.http.get(EVALUATORS)).json() == []
		assert (await api.http.get(f"{EVALUATORS}/{evaluator_id}")).status_code == 404
		assert (await api.http.delete(f"{EVALUATORS}/{evaluator_id}")).status_code == 404
		assert (await api.http.post(EVALUATORS, json=EXACT)).status_code == 201  # the same name is free in another org


async def test_only_admins_may_use_evaluators_and_runs(tenants):
	async with Api(tenants.a, tenants.user_a, role="developer") as api:
		someone = str(uuid.uuid4())
		calls = [api.http.get(EVALUATORS), api.http.post(EVALUATORS, json=EXACT), api.http.get(f"{EVALUATORS}/{someone}"),
		         api.http.delete(f"{EVALUATORS}/{someone}"), api.http.get(RUNS), api.http.get(f"{RUNS}/{someone}"),
		         api.http.get(f"{RUNS}/{someone}/items"), api.http.post(f"{RUNS}/{someone}/cancel"),
		         api.http.post(RUNS, json={"dataset_id": someone, "evaluator_id": someone, "candidate_model": "openai/gpt-4o-mini"})]
		assert [(await c).status_code for c in calls] == [403] * 9


# -- creating a run ----------------------------------------------------------------------------------


async def test_a_run_is_accepted_queued_with_its_item_count_and_cap_and_started_in_the_background(tenants, started):
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api, [("q1", "a1"), ("q2", "a2"), ("q3", "a3")])
		evaluator_id = await make_evaluator(api)
		created = await start_run(api, dataset_id, evaluator_id, max_items=2, max_cost_usd=0.5)
	assert created.status_code == 202
	run = created.json()
	assert (run["status"], run["total_items"], run["completed_items"], run["max_cost_usd"], run["mean_score"]) == ("queued", 2, 0, 0.5, None)
	assert run["evaluator"] == {"name": "exact-match", "type": "exact", "config": {"case_sensitive": False, "strip": True}}
	assert len(started) == 1 and started[0][2] == tenants.user_a.id


@pytest.mark.parametrize(
	"body,code",
	[
		({"max_items": 0}, 422), ({"max_items": 501}, 422), ({"max_cost_usd": 0}, 422), ({"max_cost_usd": 51}, 422),
		({"candidate_model": "gpt-4o"}, 422), ({"surprise": 1}, 422),
	],
)
async def test_malformed_run_requests_are_refused(tenants, started, body, code):
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api, [("q", "a")])
		refused = await start_run(api, dataset_id, await make_evaluator(api), **body)
	assert refused.status_code == code and started == []


async def test_unknown_or_foreign_datasets_and_evaluators_are_404_and_an_empty_dataset_is_422(tenants, started):
	user_b = await make_user(tenants.b)
	async with Api(tenants.b, user_b) as api_b:
		foreign_dataset = await make_dataset(api_b, [("q", "a")], name="theirs")
		foreign_evaluator = await make_evaluator(api_b)
	async with Api(tenants.a, tenants.user_a) as api:
		empty = await make_dataset(api, [], name="empty")
		mine = await make_dataset(api, [("q", "a")], name="mine")
		evaluator_id = await make_evaluator(api)
		assert (await start_run(api, foreign_dataset, evaluator_id)).status_code == 404
		assert (await start_run(api, mine, foreign_evaluator)).status_code == 404
		assert (await start_run(api, str(uuid.uuid4()), evaluator_id)).status_code == 404
		refused = await start_run(api, empty, evaluator_id)
		assert refused.status_code == 422 and refused.json()["detail"]["error"] == "empty_dataset"
	assert started == []


async def test_at_most_two_runs_are_active_at_once(tenants, started):
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id, evaluator_id = await make_dataset(api, [("q", "a")]), None
		evaluator_id = await make_evaluator(api)
		assert [(await start_run(api, dataset_id, evaluator_id)).status_code for _ in range(2)] == [202, 202]
		third = await start_run(api, dataset_id, evaluator_id)
	assert third.status_code == 409 and third.json()["detail"]["error"] == "too_many_runs" and len(started) == 2


async def test_a_model_the_org_does_not_allow_cannot_be_the_candidate_or_the_judge(tenants, started):
	async with SystemSessionLocal() as session:
		await session.execute(
			text("UPDATE organizations SET settings = jsonb_set(coalesce(settings, '{}'::jsonb), '{policy}', CAST(:p AS jsonb)) WHERE id = :id"),
			{"p": '{"enforcement_mode": "enforce", "allowed_models": ["openai/gpt-4o-mini"]}', "id": tenants.a},
		)
		await session.commit()
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api, [("q", "a")])
		exact_id, judge_id = await make_evaluator(api), await make_evaluator(api, JUDGE)  # the judge uses openai/gpt-4o
		candidate_refused = await start_run(api, dataset_id, exact_id, candidate_model="openai/gpt-4o")
		judge_refused = await start_run(api, dataset_id, judge_id)
		allowed = await start_run(api, dataset_id, exact_id)
	assert candidate_refused.json()["detail"]["error"] == judge_refused.json()["detail"]["error"] == "model_not_allowed"
	assert allowed.status_code == 202


async def test_the_system_prompt_comes_from_the_template_unless_one_is_given(tenants, started):
	async with org_scoped_session(tenants.a) as db:
		template = PromptTemplate(org_id=tenants.a, name="support", system_message="You are a support agent.", user_template="{{q}}",
		                          variables_schema=[], version=1, is_active=True, created_by=tenants.user_a.id)
		db.add(template)
		await db.commit()
		template_id = str(template.id)
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id, evaluator_id = await make_dataset(api, [("q", "a")]), None
		evaluator_id = await make_evaluator(api)
		from_template = (await start_run(api, dataset_id, evaluator_id, prompt_template_id=template_id)).json()["id"]
		await api.http.post(f"{RUNS}/{from_template}/cancel")
		explicit = (await start_run(api, dataset_id, evaluator_id, prompt_template_id=template_id, system_prompt="Be brief.")).json()["id"]
		assert (await start_run(api, dataset_id, evaluator_id, prompt_template_id=str(uuid.uuid4()))).status_code == 404
	async with org_scoped_session(tenants.a) as db:
		prompts = {str(r.id): r.system_prompt for r in await db.scalars(select(EvalRun))}
	assert prompts[from_template] == "You are a support agent." and prompts[explicit] == "Be brief."


# -- executing a run ---------------------------------------------------------------------------------


async def test_a_run_scores_every_item_and_reports_the_average_and_pass_rate(tenants, started, models):
	models.answers = {"q1": "a1", "q2": "a2", "q3": "wrong"}
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api, [("q1", "a1"), ("q2", "a2"), ("q3", "a3")])
		final = await run_to_the_end(api, started, tenants.user_a, dataset_id=dataset_id, evaluator_id=await make_evaluator(api))
		items = (await api.http.get(f"{RUNS}/{final['id']}/items")).json()
	assert (final["status"], final["completed_items"], final["scored_items"], final["failed_items"], final["passed_items"]) == ("completed", 3, 3, 0, 2)
	assert final["mean_score"] == pytest.approx(2 / 3) and final["pass_rate"] == pytest.approx(2 / 3)
	assert final["cost_usd"] == pytest.approx(0.3) and final["started_at"] and final["finished_at"]
	assert sorted((i["output"], i["passed"]) for i in items) == [("a1", True), ("a2", True), ("wrong", False)]
	assert all(i["latency_ms"] == 12 and i["error"] is None for i in items)


async def test_the_system_prompt_is_sent_first_and_each_call_is_tagged_with_its_run(tenants, started, models):
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api, [("q1", "a1")])
		final = await run_to_the_end(api, started, tenants.user_a, dataset_id=dataset_id, evaluator_id=await make_evaluator(api), system_prompt="Be brief.")
	[call] = models.calls
	assert call["messages"] == [{"role": "system", "content": "Be brief."}, {"role": "user", "content": "q1"}]
	assert call["model"] == "openai/gpt-4o-mini" and call["source"] == "eval_run" and call["extra_metadata"] == {"eval_run_id": final["id"]}


async def test_items_that_could_not_be_scored_are_recorded_with_why_and_left_out_of_the_average(tenants, started, models):
	models.answers = {"q1": "a1", "q2": RunOutcome(error="Blocked by policy.", refused=True), "q3": RunOutcome(error="upstream exploded")}
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api, [("q1", "a1"), ("q2", "a2"), ("q3", "a3")])
		final = await run_to_the_end(api, started, tenants.user_a, dataset_id=dataset_id, evaluator_id=await make_evaluator(api))
		errors = (await api.http.get(f"{RUNS}/{final['id']}/items", params={"outcome": "error"})).json()
	assert (final["status"], final["completed_items"], final["scored_items"], final["failed_items"]) == ("completed", 3, 1, 2)
	assert final["mean_score"] == 1.0 and final["pass_rate"] == 1.0  # over the one item that could be scored, not diluted by zeros
	assert sorted(e["error"] for e in errors) == ["Blocked by policy.", "upstream exploded"] and all(e["score"] is None for e in errors)


async def test_an_item_with_no_expected_answer_is_an_error_for_the_exact_evaluator_not_a_failure(tenants, started, models):
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api, [("q1", None)])
		final = await run_to_the_end(api, started, tenants.user_a, dataset_id=dataset_id, evaluator_id=await make_evaluator(api))
		[item] = (await api.http.get(f"{RUNS}/{final['id']}/items")).json()
	assert final["failed_items"] == 1 and final["mean_score"] is None and "expected" in item["error"]


async def test_the_judge_scores_the_items_and_its_cost_counts_toward_the_run(tenants, started, models):
	models.judge_score = 4
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api, [("q1", None), ("q2", None)])
		final = await run_to_the_end(api, started, tenants.user_a, dataset_id=dataset_id, evaluator_id=await make_evaluator(api, JUDGE))
	assert (final["status"], final["passed_items"]) == ("completed", 2) and final["mean_score"] == 0.75
	assert final["cost_usd"] == pytest.approx(2 * (0.1 + 0.05))
	assert len(models.judge_calls) == 2 and models.judge_calls[0]["source"] == "eval_judge"


async def test_the_run_stops_when_its_spending_cap_is_reached(tenants, started, models):
	models.cost = Decimal("0.4")
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api, [(f"q{i}", f"a{i}") for i in range(5)])
		final = await run_to_the_end(api, started, tenants.user_a, dataset_id=dataset_id, evaluator_id=await make_evaluator(api), max_cost_usd=1.0)
	assert final["status"] == "budget_exceeded" and final["completed_items"] == 3 and len(models.calls) == 3
	assert final["cost_usd"] == pytest.approx(1.2)  # the third item crossed the cap; no fourth started


async def test_a_cancelled_run_starts_no_new_items_and_stays_cancelled(tenants, started, models):
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api, [(f"q{i}", f"a{i}") for i in range(5)])
		evaluator_id = await make_evaluator(api)
		created = await start_run(api, dataset_id, evaluator_id)
		run_id = created.json()["id"]

		async def cancel_after_two(count):
			if count == 2:
				assert (await api.http.post(f"{RUNS}/{run_id}/cancel")).status_code == 200

		models.on_call = cancel_after_two
		[(rid, org_id, user_id, redis)] = started
		await eval_runner.execute_run(rid, org_id, user_id, redis)
		final = (await api.http.get(f"{RUNS}/{run_id}")).json()
		again = await api.http.post(f"{RUNS}/{run_id}/cancel")
	assert final["status"] == "cancelled" and final["completed_items"] == 2 and len(models.calls) == 2
	assert again.status_code == 409 and again.json()["detail"]["error"] == "run_finished"


async def test_an_error_before_any_item_runs_ends_the_run_as_failed_with_the_reason(tenants, started, models, monkeypatch):
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api, [("q1", "a1")])
		created = await start_run(api, dataset_id, await make_evaluator(api))
		run_id = created.json()["id"]

		async def broken(*args, **kwargs):
			raise RuntimeError("policy store is down")

		monkeypatch.setattr(eval_runner.policy_store, "load", broken)  # only for execution; creating the run needs it too
		[(rid, org_id, user_id, redis)] = started
		await eval_runner.execute_run(rid, org_id, user_id, redis)
		final = (await api.http.get(f"{RUNS}/{run_id}")).json()
	assert final["status"] == "failed" and "policy store is down" in final["error"] and models.calls == []


async def test_a_run_that_is_not_queued_is_not_executed_twice(tenants, started, models):
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api, [("q1", "a1")])
		final = await run_to_the_end(api, started, tenants.user_a, dataset_id=dataset_id, evaluator_id=await make_evaluator(api))
		[(rid, org_id, user_id, redis)] = started
		await eval_runner.execute_run(rid, org_id, user_id, redis)
	assert final["status"] == "completed" and len(models.calls) == 1


async def test_deleting_the_evaluator_leaves_finished_runs_readable(tenants, started, models):
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id, evaluator_id = await make_dataset(api, [("q1", "a1")]), None
		evaluator_id = await make_evaluator(api)
		final = await run_to_the_end(api, started, tenants.user_a, dataset_id=dataset_id, evaluator_id=evaluator_id)
		assert (await api.http.delete(f"{EVALUATORS}/{evaluator_id}")).status_code == 204
		after = (await api.http.get(f"{RUNS}/{final['id']}")).json()
	assert after["evaluator_id"] is None and after["evaluator"]["name"] == "exact-match" and after["mean_score"] == final["mean_score"]


async def test_another_orgs_run_does_not_exist_for_you(tenants, started, models):
	user_b = await make_user(tenants.b)
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api, [("q1", "a1")])
		final = await run_to_the_end(api, started, tenants.user_a, dataset_id=dataset_id, evaluator_id=await make_evaluator(api))
	async with Api(tenants.b, user_b) as api:
		assert (await api.http.get(RUNS)).json() == []
		statuses = [(await c).status_code for c in (api.http.get(f"{RUNS}/{final['id']}"), api.http.get(f"{RUNS}/{final['id']}/items"),
		                                            api.http.post(f"{RUNS}/{final['id']}/cancel"))]
	assert statuses == [404, 404, 404]


async def test_item_results_can_be_filtered_and_paged(tenants, started, models):
	models.answers = {"q1": "a1", "q2": "nope", "q3": "a3", "q4": RunOutcome(error="boom")}
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api, [("q1", "a1"), ("q2", "a2"), ("q3", "a3"), ("q4", "a4")])
		final = await run_to_the_end(api, started, tenants.user_a, dataset_id=dataset_id, evaluator_id=await make_evaluator(api))
		url = f"{RUNS}/{final['id']}/items"
		counts = {o: len((await api.http.get(url, params={"outcome": o})).json()) for o in ("passed", "failed", "error")}
		everything = (await api.http.get(url)).json()
		paged = (await api.http.get(url, params={"limit": 3})).json() + (await api.http.get(url, params={"limit": 3, "offset": 3})).json()
		bad_filter = await api.http.get(url, params={"outcome": "weird"})
	assert counts == {"passed": 2, "failed": 1, "error": 1} and len(everything) == 4
	assert [i["id"] for i in paged] == [i["id"] for i in everything] and bad_filter.status_code == 422


async def test_creating_and_cancelling_runs_and_evaluators_are_in_the_admin_audit_log(tenants, started):
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id = await make_dataset(api, [("q1", "a1")])
		evaluator_id = await make_evaluator(api)
		run_id = (await start_run(api, dataset_id, evaluator_id)).json()["id"]
		await api.http.post(f"{RUNS}/{run_id}/cancel")
		await api.http.delete(f"{EVALUATORS}/{evaluator_id}")
	async with org_scoped_session(tenants.a) as db:
		actions = set(await db.scalars(select(AdminAuditLog.action).where(AdminAuditLog.org_id == tenants.a, AdminAuditLog.resource_type.in_(("evaluator", "eval_run")))))
	assert actions == {"evaluator.created", "evaluator.deleted", "eval_run.created", "eval_run.cancelled"}


# -- stale runs ----------------------------------------------------------------------------------------


async def test_runs_left_active_long_after_they_could_have_finished_are_ended_and_recent_ones_are_not(tenants, started):
	async with Api(tenants.a, tenants.user_a) as api:
		dataset_id, evaluator_id = await make_dataset(api, [("q1", "a1")]), None
		evaluator_id = await make_evaluator(api)
		old, recent = [(await start_run(api, dataset_id, evaluator_id)).json()["id"] for _ in range(2)]
	async with SystemSessionLocal() as session:
		stale_age = eval_runner.STALE_AFTER + timedelta(hours=1)
		await session.execute(text("UPDATE eval_runs SET created_at = now() - make_interval(secs => :s) WHERE id = :id"),
		                      {"s": stale_age.total_seconds(), "id": old})
		await session.commit()
	assert await eval_runner.fail_stale_runs() >= 1
	async with Api(tenants.a, tenants.user_a) as api:
		old_run, recent_run = (await api.http.get(f"{RUNS}/{old}")).json(), (await api.http.get(f"{RUNS}/{recent}")).json()
	assert old_run["status"] == "failed" and "interrupted" in old_run["error"] and recent_run["status"] == "queued"
