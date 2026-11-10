"""Adaptive A/B experiments against the real schema: the API, the periodic job and the per-variant results (slice 5)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.database import org_scoped_session
from app.models.admin_audit_log import AdminAuditLog
from app.models.request_log import RequestLog
from app.models.request_score import RequestScore
from app.services.adaptive_experiments import SYSTEM_ACTOR, update_adaptive_experiments
from tests.db_helpers import Api, make_user, remove_seeded_logs  # noqa: F401  (an autouse fixture: removes seeded request_logs)
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)

PATH = "/api/v1/experiments"
ADAPTIVE = {"mode": "adaptive", "metric": "thumbs"}


def body(**overrides):
	return {
		"name": f"exp-{uuid.uuid4().hex[:6]}", "target_model": "openai/gpt-4o",
		"variants": [{"model": "openai/gpt-4o-mini", "traffic_weight": 50}, {"model": "openai/gpt-4o", "traffic_weight": 50}],
		**ADAPTIVE, **overrides,
	}


async def create(api, **overrides) -> dict:
	created = await api.http.post(PATH, json=body(**overrides))
	assert created.status_code in (200, 201), created.text
	return created.json()


async def score(org_id, experiment, variant_index, values) -> None:
	"""Feedback for one variant: a list of 0/1 (or other) values, each on its own request."""
	variant_id = uuid.UUID(experiment["variants"][variant_index]["id"])
	async with org_scoped_session(org_id) as db:
		for value in values:
			db.add(RequestScore(request_id=uuid.uuid4(), org_id=org_id, experiment_id=uuid.UUID(experiment["id"]), variant_id=variant_id,
			                    score_name="thumbs", value=value))
		await db.commit()


def thumbs(up, down):
	return [1] * up + [0] * down


async def get(api, experiment_id) -> dict:
	return (await api.http.get(f"{PATH}/{experiment_id}")).json()


def weights(experiment) -> dict[str, int]:
	"""Traffic weight by variant id. Compare these, not list positions: nothing promises the order a client sees."""
	return {v["id"]: v["traffic_weight"] for v in experiment["variants"]}


# -- the API ---------------------------------------------------------------------------------------


async def test_an_adaptive_experiment_is_created_with_the_safe_defaults(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		experiment = await create(api)
	assert (experiment["mode"], experiment["metric"], experiment["min_samples_per_variant"], experiment["delta"], experiment["weight_floor"]) == ("adaptive", "thumbs", 30, 0.01, 5)
	assert experiment["winner_variant_id"] is None and experiment["stopped_reason"] is None and experiment["is_active"] is True


async def test_an_ordinary_experiment_is_still_static(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		plain = (await api.http.post(PATH, json={"name": "plain", "target_model": "openai/gpt-4o", "variants": [{"model": "openai/gpt-4o-mini", "traffic_weight": 100}]})).json()
	assert (plain["mode"], plain["metric"]) == ("static", None)


@pytest.mark.parametrize(
	"overrides,message",
	[
		({"metric": None}, "needs a metric"),
		({"variants": [{"model": "openai/gpt-4o-mini", "traffic_weight": 100}]}, "at least two variants"),
		({"weight_floor": 20, "variants": [{"model": f"openai/m{i}", "traffic_weight": 20} for i in range(6)]}, "more than 100%"),
	],
)
async def test_an_adaptive_experiment_that_could_not_run_is_refused_with_why(tenants, overrides, message):
	async with Api(tenants.a, tenants.user_a) as api:
		refused = await api.http.post(PATH, json=body(**overrides))
	assert refused.status_code == 422 and refused.json()["detail"]["error"] == "invalid_adaptive_experiment" and message in refused.json()["detail"]["detail"]


@pytest.mark.parametrize("overrides", [{"min_samples_per_variant": 19}, {"delta": 0}, {"delta": 0.5}, {"weight_floor": 0}, {"weight_floor": 21},
                                       {"mode": "sometimes"}, {"metric": "has space"}])
async def test_out_of_range_adaptive_settings_are_refused(tenants, overrides):
	async with Api(tenants.a, tenants.user_a) as api:
		assert (await api.http.post(PATH, json=body(**overrides))).status_code == 422


async def test_switching_an_experiment_to_adaptive_and_changing_its_test_forgets_an_old_result(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		experiment = await create(api, mode="static", metric=None)
		turned_on = await api.http.patch(f"{PATH}/{experiment['id']}", json={"mode": "adaptive", "metric": "thumbs"})
		assert turned_on.status_code == 200 and turned_on.json()["mode"] == "adaptive"
		no_metric = await api.http.patch(f"{PATH}/{experiment['id']}", json={"metric": None})
		assert no_metric.status_code == 422  # still adaptive, so it still needs one


async def test_stopping_by_hand_is_recorded_as_manual_and_starting_again_clears_it(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		experiment = await create(api)
		stopped = (await api.http.post(f"{PATH}/{experiment['id']}/stop")).json()
		started = (await api.http.post(f"{PATH}/{experiment['id']}/start")).json()
	assert (stopped["is_active"], stopped["stopped_reason"]) == (False, "manual")
	assert (started["is_active"], started["stopped_reason"], started["winner_variant_id"]) == (True, None, None)


# -- the job ---------------------------------------------------------------------------------------


async def test_nothing_moves_before_every_variant_has_enough_feedback(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		experiment = await create(api)
		await score(tenants.a, experiment, 0, thumbs(100, 0))  # a landslide for variant 0 ...
		await score(tenants.a, experiment, 1, thumbs(0, 29))  # ... but variant 1 has 29 of the 30 needed
		assert await update_adaptive_experiments() >= 1
		after = await get(api, experiment["id"])
	assert [v["traffic_weight"] for v in after["variants"]] == [50, 50]
	assert after["is_active"] is True and after["winner_variant_id"] is None and after["adaptive_error"] is None and after["adaptive_updated_at"]


async def test_a_clear_winner_stops_the_test_and_is_recorded_but_not_deployed(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		experiment = await create(api)
		await score(tenants.a, experiment, 0, thumbs(15, 55))  # 21% liked
		await score(tenants.a, experiment, 1, thumbs(56, 14))  # 80% liked
		await update_adaptive_experiments()
		after = await get(api, experiment["id"])
	assert after["is_active"] is False and after["stopped_reason"] == "winner"
	assert after["winner_variant_id"] == experiment["variants"][1]["id"]
	assert after["target_model"] == "openai/gpt-4o"  # the model production traffic goes to is untouched
	async with org_scoped_session(tenants.a) as db:
		entry = await db.scalar(select(AdminAuditLog).where(AdminAuditLog.resource_id == experiment["id"], AdminAuditLog.action == "experiment.winner_found"))
	assert entry is not None and entry.actor_email == SYSTEM_ACTOR and entry.actor_id is None


async def test_a_close_race_shifts_traffic_but_keeps_testing(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		experiment = await create(api, delta=0.001)
		await score(tenants.a, experiment, 0, thumbs(40, 40))
		await score(tenants.a, experiment, 1, thumbs(50, 30))
		await update_adaptive_experiments()
		after = await get(api, experiment["id"])
	by_id = weights(after)
	weak, strong = (experiment["variants"][i]["id"] for i in (0, 1))
	assert after["is_active"] is True and after["winner_variant_id"] is None
	assert sum(by_id.values()) == 100 and all(w >= 5 for w in by_id.values()) and by_id[strong] > by_id[weak]
	async with org_scoped_session(tenants.a) as db:
		actions = set(await db.scalars(select(AdminAuditLog.action).where(AdminAuditLog.resource_id == experiment["id"])))
	assert "experiment.weights_adapted" in actions


async def test_the_floor_keeps_a_losing_variant_in_the_game(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		experiment = await create(api, delta=0.001, weight_floor=10)
		await score(tenants.a, experiment, 0, thumbs(30, 30))
		await score(tenants.a, experiment, 1, thumbs(33, 27))
		await update_adaptive_experiments()
		by_id = weights(await get(api, experiment["id"]))
	assert min(by_id.values()) >= 10 and sum(by_id.values()) == 100


async def test_static_and_stopped_experiments_are_left_alone(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		static = await create(api, mode="static", target_model="openai/gpt-4o")  # keeps its metric: switching modes does
		stopped = await create(api, target_model="openai/gpt-4-turbo")  # only one active experiment per target model
		await api.http.post(f"{PATH}/{stopped['id']}/stop")
		for experiment in (static, stopped):
			await score(tenants.a, experiment, 0, thumbs(10, 60))
			await score(tenants.a, experiment, 1, thumbs(60, 10))
		await update_adaptive_experiments()
		after = [await get(api, e["id"]) for e in (static, stopped)]
	assert [[v["traffic_weight"] for v in a["variants"]] for a in after] == [[50, 50], [50, 50]]
	assert [a["winner_variant_id"] for a in after] == [None, None]


async def test_a_metric_that_is_not_a_rate_is_an_error_not_a_guess(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		experiment = await create(api)
		await score(tenants.a, experiment, 0, [4.5] * 40)  # a 1-5 rating, not a 0-1 rate
		await score(tenants.a, experiment, 1, [3.0] * 40)
		await update_adaptive_experiments()
		after = await get(api, experiment["id"])
	assert "outside 0 to 1" in after["adaptive_error"] and after["is_active"] is True
	assert [v["traffic_weight"] for v in after["variants"]] == [50, 50] and after["winner_variant_id"] is None


async def test_each_orgs_experiments_are_decided_from_its_own_feedback_only(tenants):
	user_b = await make_user(tenants.b)
	async with Api(tenants.a, tenants.user_a) as api_a:
		mine = await create(api_a)
	async with Api(tenants.b, user_b) as api_b:  # one pinned caller at a time: the dependency overrides are global
		theirs = await create(api_b)
	await score(tenants.b, theirs, 0, thumbs(10, 60))
	await score(tenants.b, theirs, 1, thumbs(60, 10))
	await update_adaptive_experiments()
	async with Api(tenants.a, tenants.user_a) as api_a:
		mine_after = await get(api_a, mine["id"])
	async with Api(tenants.b, user_b) as api_b:
		theirs_after = await get(api_b, theirs["id"])
	assert mine_after["winner_variant_id"] is None and mine_after["is_active"] is True  # no feedback of its own
	assert theirs_after["winner_variant_id"] == theirs["variants"][1]["id"]


async def test_running_the_job_twice_changes_nothing_the_second_time(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		experiment = await create(api, delta=0.001)
		await score(tenants.a, experiment, 0, thumbs(40, 40))
		await score(tenants.a, experiment, 1, thumbs(50, 30))
		await update_adaptive_experiments()
		first = weights(await get(api, experiment["id"]))
		await update_adaptive_experiments()
		second = weights(await get(api, experiment["id"]))
	assert first == second


# -- results, keyed by variant ----------------------------------------------------------------------


async def seed_logs(org_id, user_id, experiment, variant_index, count, model="openai/gpt-4o-mini"):
	async with org_scoped_session(org_id) as db:
		for _ in range(count):
			db.add(RequestLog(
				request_id=uuid.uuid4(), org_id=org_id, user_id=user_id, model=model, provider="openai", status_code=200, latency_ms=100,
				request_metadata={"experiment": {"experiment_id": experiment["id"], "variant_id": experiment["variants"][variant_index]["id"]}},
			))
		await db.commit()


async def test_two_variants_on_the_same_model_are_reported_separately(tenants):
	"""The results used to be keyed by model name, so two variants running the same model collapsed into one row."""
	async with Api(tenants.a, tenants.user_a) as api:
		experiment = await create(api, variants=[{"model": "openai/gpt-4o-mini", "traffic_weight": 50}, {"model": "openai/gpt-4o-mini", "traffic_weight": 50}])
		await seed_logs(tenants.a, tenants.user_a.id, experiment, 0, 3)
		await seed_logs(tenants.a, tenants.user_a.id, experiment, 1, 5)
		await score(tenants.a, experiment, 0, thumbs(1, 2))
		await score(tenants.a, experiment, 1, thumbs(4, 1))
		results = (await api.http.get(f"{PATH}/{experiment['id']}/results")).json()
	by_id = {v["variant_id"]: v for v in results["variants"]}
	first, second = (by_id[experiment["variants"][i]["id"]] for i in (0, 1))
	assert (first["request_count"], second["request_count"]) == (3, 5)
	assert first["scores"] == [{"name": "thumbs", "avg": pytest.approx(1 / 3), "count": 3}]
	assert second["scores"] == [{"name": "thumbs", "avg": pytest.approx(0.8), "count": 5}]
	assert first["traffic_weight"] == second["traffic_weight"] == 50


async def test_adaptive_results_say_how_far_along_the_test_is(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		experiment = await create(api)
		await seed_logs(tenants.a, tenants.user_a.id, experiment, 0, 1)
		await score(tenants.a, experiment, 0, thumbs(10, 10))
		await score(tenants.a, experiment, 1, thumbs(18, 2))
		results = (await api.http.get(f"{PATH}/{experiment['id']}/results")).json()
	adaptive = results["adaptive"]
	assert adaptive["metric"] == "thumbs" and adaptive["ready"] is False and adaptive["min_samples_per_variant"] == 30
	assert adaptive["samples"] == {experiment["variants"][0]["id"]: 20, experiment["variants"][1]["id"]: 20}
	assert adaptive["winner_variant_id"] is None and adaptive["error"] is None
	assert results["variants"][0]["probability_best"] is not None


async def test_a_static_experiments_results_have_no_adaptive_block(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		experiment = await create(api, mode="static", metric=None)
		results = (await api.http.get(f"{PATH}/{experiment['id']}/results")).json()
	assert results["adaptive"] is None


async def test_old_log_rows_without_a_variant_id_are_matched_by_model_when_that_is_unambiguous(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		experiment = await create(api, mode="static", metric=None)
		async with org_scoped_session(tenants.a) as db:
			db.add(RequestLog(request_id=uuid.uuid4(), org_id=tenants.a, user_id=tenants.user_a.id, model="openai/gpt-4o-mini", provider="openai",
			                  status_code=200, request_metadata={"experiment": {"experiment_id": experiment["id"]}}))
			await db.commit()
		results = (await api.http.get(f"{PATH}/{experiment['id']}/results")).json()
	[row] = results["variants"]
	mini = next(v for v in experiment["variants"] if v["model"] == "openai/gpt-4o-mini")  # by model: the list order is by id
	assert row["variant_id"] == mini["id"] and row["traffic_weight"] == 50
