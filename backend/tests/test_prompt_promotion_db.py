"""The prompt promotion gate against the real schema: drafts, promotion, override, and every way a run can fail to count (slice 6)."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text

from app.database import SystemSessionLocal, org_scoped_session
from app.models.admin_audit_log import AdminAuditLog
from app.models.evaluation import EvalRun
from app.models.prompt_template import PromptTemplate
from app.services import eval_runner
from app.services.llm_service import _resolve_prompt_template
from app.services.prompt_gate import fingerprint
from tests.conftest import FakeRedis
from tests.db_helpers import Api, make_user
from tests.test_mcp_pinning_db import _dispose_app_engines, pytestmark  # noqa: F401  (shared DB test setup)

TEMPLATES = "/api/v1/prompt-templates"
PROMPT = {"name": "support", "system_message": "You are a concise support agent.", "user_template": "{{question}}"}


async def set_policy(org_id, **fields):
	"""Merge fields into the org's stored policy (the route reads it through the policy store)."""
	async with SystemSessionLocal() as session:
		await session.execute(
			text("UPDATE organizations SET settings = jsonb_set(coalesce(settings, '{}'::jsonb), '{policy}', "
			     "coalesce(settings->'policy', '{}'::jsonb) || CAST(:patch AS jsonb)) WHERE id = :id"),
			{"patch": json.dumps(fields), "id": org_id},
		)
		await session.commit()


def forget_cached_policy(api):
	"""The policy is cached for 60 seconds, as documented; a test that changes it mid-way needs a cold cache."""
	api.redis = FakeRedis()


async def gate_on(org_id, **fields):
	await set_policy(org_id, prompt_promotion_gate=True, **fields)


async def create(api, **overrides) -> dict:
	created = await api.http.post(TEMPLATES, json={**PROMPT, **overrides})
	assert created.status_code == 201, created.text
	return created.json()


async def row(org_id, template_id) -> PromptTemplate:
	async with org_scoped_session(org_id) as db:
		return await db.get(PromptTemplate, uuid.UUID(template_id))


async def make_run(org_id, template_id, *, fingerprint_of=None, status="completed", total=20, completed=None, failed=0, passed=18,
                   user_id=None) -> str:
	"""An eval run that tested a template, with the counters a finished run would have. ``fingerprint_of`` defaults to the template's."""
	template = await row(org_id, template_id)
	completed = total if completed is None else completed
	async with org_scoped_session(org_id) as db:
		run = EvalRun(
			org_id=org_id, evaluator_snapshot={"name": "e", "type": "exact", "config": {}}, prompt_template_id=uuid.UUID(template_id),
			prompt_fingerprint=fingerprint(template) if fingerprint_of is None else fingerprint_of, candidate_model="openai/gpt-4o-mini",
			system_prompt=template.system_message, status=status, total_items=total, completed_items=completed, failed_items=failed,
			passed_items=passed, score_sum=Decimal(passed), max_cost_usd=Decimal("1"), created_by=user_id,
		)
		db.add(run)
		await db.commit()
		return str(run.id)


async def draft_of_live(api, org_id) -> tuple[dict, dict]:
	"""A live v1 (made before the gate existed), then the gate on, then an edit: returns (v1, the v2 draft)."""
	live = await create(api)
	await gate_on(org_id)
	draft = (await api.http.put(f"{TEMPLATES}/{live['id']}", json={"system_message": "You are a very concise support agent."})).json()
	return live, draft


async def promote(api, template_id, **body):
	return await api.http.post(f"{TEMPLATES}/{template_id}/promote", json=body)


# -- the lifecycle -----------------------------------------------------------------------------------


async def test_with_the_gate_off_an_edit_goes_live_exactly_as_before(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		v1 = await create(api)
		v2 = (await api.http.put(f"{TEMPLATES}/{v1['id']}", json={"user_template": "Q: {{question}}"})).json()
		listed = (await api.http.get(TEMPLATES)).json()
	assert (v1["status"], v1["is_active"], v1["version"]) == ("active", True, 1)
	assert (v2["status"], v2["is_active"], v2["version"]) == ("active", True, 2)
	assert [(t["version"], t["status"]) for t in listed] == [(2, "active")]  # v1 is retired and no longer listed
	assert (await row(tenants.a, v1["id"])).status == "retired"


async def test_with_the_gate_on_a_new_template_starts_as_a_draft_and_is_not_live(tenants):
	await gate_on(tenants.a)
	async with Api(tenants.a, tenants.user_a) as api:
		draft = await create(api)
		listed = (await api.http.get(TEMPLATES)).json()
	assert (draft["status"], draft["is_active"]) == ("draft", False)
	assert [(t["id"], t["status"]) for t in listed] == [(draft["id"], "draft")]  # drafts are visible so they can be promoted
	async with org_scoped_session(tenants.a) as db:
		with pytest.raises(HTTPException) as refused:
			await _resolve_prompt_template(db, tenants.a, uuid.UUID(draft["id"]), {"question": "hi"})
	assert refused.value.status_code == 404 and refused.value.detail["error"] == "prompt_not_found"  # a client cannot use a draft


async def test_with_the_gate_on_an_edit_makes_a_draft_and_the_live_version_keeps_serving(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		live, draft = await draft_of_live(api, tenants.a)
		listed = {t["version"]: t["status"] for t in (await api.http.get(TEMPLATES)).json()}
	assert (draft["status"], draft["version"], draft["is_active"]) == ("draft", 2, False)
	assert listed == {1: "active", 2: "draft"} and (await row(tenants.a, live["id"])).is_active is True
	async with org_scoped_session(tenants.a) as db:
		messages = await _resolve_prompt_template(db, tenants.a, uuid.UUID(live["id"]), {"question": "hi"})
	assert messages[0].content == "You are a concise support agent."  # still the old prompt


async def test_only_one_draft_per_prompt_and_editing_it_changes_it_in_place(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		live, draft = await draft_of_live(api, tenants.a)
		second = await api.http.put(f"{TEMPLATES}/{live['id']}", json={"user_template": "other"})
		in_place = (await api.http.put(f"{TEMPLATES}/{draft['id']}", json={"user_template": "Q: {{question}}"})).json()
	assert second.status_code == 409 and second.json()["detail"]["error"] == "draft_exists"
	assert (in_place["id"], in_place["version"], in_place["status"], in_place["user_template"]) == (draft["id"], 2, "draft", "Q: {{question}}")


async def test_deleting_a_draft_retires_it(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		_, draft = await draft_of_live(api, tenants.a)
		assert (await api.http.delete(f"{TEMPLATES}/{draft['id']}")).status_code == 204
		assert {t["version"] for t in (await api.http.get(TEMPLATES)).json()} == {1}
	assert (await row(tenants.a, draft["id"])).status == "retired"


# -- promotion --------------------------------------------------------------------------------------


async def test_a_draft_with_no_eval_run_cannot_be_promoted_and_the_refusal_says_what_to_do(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		_, draft = await draft_of_live(api, tenants.a)
		refused = await promote(api, draft["id"])
	body = refused.json()["detail"]
	assert refused.status_code == 409 and body["error"] == "promotion_gate_failed"
	assert "no eval run has tested this exact prompt" in body["reasons"][0] and body["requirements"] == {"min_pass_rate": 0.8, "min_items": 10}
	assert (await row(tenants.a, draft["id"])).status == "draft"


async def test_a_run_that_passed_but_not_well_enough_is_refused_with_the_closest_run_shown(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		_, draft = await draft_of_live(api, tenants.a)
		run_id = await make_run(tenants.a, draft["id"], passed=12)  # 12 of 20: 60%
		refused = await promote(api, draft["id"])
	body = refused.json()["detail"]
	assert refused.status_code == 409 and any("60%" in r for r in body["reasons"]) and body["best_run"]["run_id"] == run_id
	assert body["best_run"]["pass_rate"] == pytest.approx(0.6)


async def test_a_run_that_vouches_for_the_draft_promotes_it_and_retires_the_old_version(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		live, draft = await draft_of_live(api, tenants.a)
		run_id = await make_run(tenants.a, draft["id"], passed=18)
		promoted = await promote(api, draft["id"])
		listed = {t["version"]: t["status"] for t in (await api.http.get(TEMPLATES)).json()}
	assert promoted.status_code == 200, promoted.text
	assert promoted.json() | {"template_id": None} == {"template_id": None, "name": "support", "version": 2, "status": "active",
	                                                       "previous_version": 1, "run_id": run_id, "overridden": False}
	assert listed == {2: "active"} and (await row(tenants.a, live["id"])).is_active is False
	async with org_scoped_session(tenants.a) as db:
		messages = await _resolve_prompt_template(db, tenants.a, uuid.UUID(draft["id"]), {"question": "hi"})
		entry = await db.scalar(select(AdminAuditLog).where(AdminAuditLog.org_id == tenants.a, AdminAuditLog.action == "prompt_template.promoted"))
	assert messages[0].content == "You are a very concise support agent." and entry.after["run_id"] == run_id and entry.after["pass_rate"] == 0.9


@pytest.mark.parametrize(
	"run,why",
	[
		({"status": "cancelled"}, "cancelled"),
		({"status": "budget_exceeded"}, "budget_exceeded"),
		({"status": "failed"}, "failed"),
		({"total": 8, "passed": 8}, "only 8 items were scored"),
		({"total": 30, "completed": 30, "failed": 10, "passed": 20}, "could not be scored"),
	],
)
async def test_a_run_that_does_not_meet_the_bar_never_promotes(tenants, run, why):
	async with Api(tenants.a, tenants.user_a) as api:
		_, draft = await draft_of_live(api, tenants.a)
		await make_run(tenants.a, draft["id"], **run)
		refused = await promote(api, draft["id"])
	assert refused.status_code == 409 and why in " ".join(refused.json()["detail"]["reasons"])


async def test_editing_the_draft_after_its_run_means_the_run_no_longer_counts(tenants):
	await gate_on(tenants.a)
	async with Api(tenants.a, tenants.user_a) as api:
		draft = await create(api)
		await make_run(tenants.a, draft["id"])
		assert (await api.http.get(f"{TEMPLATES}/{draft['id']}/promotion")).json()["passes_gate"] is True
		await api.http.put(f"{TEMPLATES}/{draft['id']}", json={"system_message": "Changed after the run."})  # a draft is edited in place
		refused = await promote(api, draft["id"])
	assert refused.status_code == 409 and "no eval run has tested this exact prompt" in refused.json()["detail"]["reasons"][0]


async def test_a_run_of_a_different_prompt_or_with_another_fingerprint_does_not_vouch(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		_, draft = await draft_of_live(api, tenants.a)
		other = await create(api, name="unrelated")
		await make_run(tenants.a, other["id"])  # a perfect run, of another prompt
		await make_run(tenants.a, draft["id"], fingerprint_of="0" * 64)  # a run of something else that was filed under this prompt
		refused = await promote(api, draft["id"])
	assert refused.status_code == 409 and "no eval run has tested this exact prompt" in refused.json()["detail"]["reasons"][0]


async def test_a_template_with_no_system_message_cannot_be_vouched_for_by_a_run(tenants):
	await gate_on(tenants.a)
	async with Api(tenants.a, tenants.user_a) as api:
		draft = await create(api, system_message=None)
		await make_run(tenants.a, draft["id"])
		refused = await promote(api, draft["id"])
		status_view = (await api.http.get(f"{TEMPLATES}/{draft['id']}/promotion")).json()
	assert refused.status_code == 409 and "no system message" in refused.json()["detail"]["reasons"][0]
	assert status_view["passes_gate"] is False and "no system message" in status_view["reasons"][0]


async def test_the_thresholds_are_the_orgs_to_set(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		_, draft = await draft_of_live(api, tenants.a)
		await set_policy(tenants.a, prompt_gate_min_pass_rate=0.95, prompt_gate_min_items=30)
		forget_cached_policy(api)
		await make_run(tenants.a, draft["id"], total=20, passed=19)  # 95% but only 20 items
		strict = await promote(api, draft["id"])
		await set_policy(tenants.a, prompt_gate_min_pass_rate=0.9, prompt_gate_min_items=20)
		forget_cached_policy(api)
		relaxed = await promote(api, draft["id"])
	assert strict.status_code == 409 and "at least 30 are required" in " ".join(strict.json()["detail"]["reasons"])
	assert relaxed.status_code == 200


# -- override ---------------------------------------------------------------------------------------


async def test_an_override_needs_a_real_reason_and_is_audited_with_it(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		_, draft = await draft_of_live(api, tenants.a)
		no_reason = await promote(api, draft["id"], override=True)
		short = await promote(api, draft["id"], override=True, reason="  urgent ")
		done = await promote(api, draft["id"], override=True, reason="Customer-facing typo fix, evaluation set is being rebuilt")
	assert no_reason.status_code == short.status_code == 422 and no_reason.json()["detail"]["error"] == "override_needs_reason"
	assert done.status_code == 200 and done.json()["overridden"] is True and done.json()["run_id"] is None
	async with org_scoped_session(tenants.a) as db:
		entry = await db.scalar(select(AdminAuditLog).where(AdminAuditLog.org_id == tenants.a, AdminAuditLog.action == "prompt_template.promoted_with_override"))
	assert entry.after["override_reason"].startswith("Customer-facing typo fix") and "no eval run" in entry.after["unmet"][0]


async def test_asking_for_an_override_when_the_gate_is_satisfied_is_not_recorded_as_one(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		_, draft = await draft_of_live(api, tenants.a)
		await make_run(tenants.a, draft["id"])
		done = await promote(api, draft["id"], override=True, reason="belt and braces, the run passed anyway")
	assert done.status_code == 200 and done.json()["overridden"] is False
	async with org_scoped_session(tenants.a) as db:
		actions = set(await db.scalars(select(AdminAuditLog.action).where(AdminAuditLog.org_id == tenants.a, AdminAuditLog.resource_type == "prompt_template")))
	assert actions == {"prompt_template.promoted"}


async def test_with_the_gate_turned_off_a_waiting_draft_can_be_promoted_without_a_run(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		_, draft = await draft_of_live(api, tenants.a)
		await set_policy(tenants.a, prompt_promotion_gate=False)
		forget_cached_policy(api)
		done = await promote(api, draft["id"])
	assert done.status_code == 200 and done.json()["overridden"] is False and done.json()["run_id"] is None


# -- who and what ------------------------------------------------------------------------------------


async def test_only_a_draft_can_be_promoted_and_only_once(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		live, draft = await draft_of_live(api, tenants.a)
		await make_run(tenants.a, draft["id"])
		assert (await promote(api, draft["id"])).status_code == 200
		again, live_one = await promote(api, draft["id"]), await promote(api, live["id"])
	assert again.status_code == live_one.status_code == 409 and again.json()["detail"]["error"] == "not_a_draft"


async def test_only_admins_promote_developers_can_look_and_other_orgs_see_nothing(tenants):
	user_b = await make_user(tenants.b)
	async with Api(tenants.a, tenants.user_a) as api:
		_, draft = await draft_of_live(api, tenants.a)
	async with Api(tenants.a, tenants.user_a, role="developer") as api:
		assert (await promote(api, draft["id"])).status_code == 403
		assert (await api.http.get(f"{TEMPLATES}/{draft['id']}/promotion")).status_code == 200
	async with Api(tenants.a, tenants.user_a, role="viewer") as api:
		assert (await api.http.get(f"{TEMPLATES}/{draft['id']}/promotion")).status_code == 403
	async with Api(tenants.b, user_b) as api:
		assert (await promote(api, draft["id"])).status_code == 404
		assert (await api.http.get(f"{TEMPLATES}/{draft['id']}/promotion")).status_code == 404


async def test_the_promotion_status_says_what_is_missing_and_what_the_bar_is(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		_, draft = await draft_of_live(api, tenants.a)
		before = (await api.http.get(f"{TEMPLATES}/{draft['id']}/promotion")).json()
		run_id = await make_run(tenants.a, draft["id"])
		after = (await api.http.get(f"{TEMPLATES}/{draft['id']}/promotion")).json()
	assert (before["gate_enabled"], before["passes_gate"], before["status"]) == (True, False, "draft") and before["reasons"]
	assert after["passes_gate"] is True and after["qualifying_run"]["run_id"] == run_id and after["reasons"] == []


async def test_without_the_gate_the_status_says_there_is_nothing_to_pass(tenants):
	async with Api(tenants.a, tenants.user_a) as api:
		live = await create(api)
		view = (await api.http.get(f"{TEMPLATES}/{live['id']}/promotion")).json()
	assert (view["gate_enabled"], view["passes_gate"], view["status"]) == (False, True, "active")


async def test_a_run_started_for_a_template_records_what_it_tested(tenants, monkeypatch):
	"""The link that makes the gate work: a run of the template's own prompt carries its fingerprint, an overridden prompt does not."""
	monkeypatch.setattr(eval_runner, "start", lambda *args: None)  # creating a run starts it; this test is about what it records
	async with Api(tenants.a, tenants.user_a) as api:
		template = await create(api)
		dataset = (await api.http.post("/api/v1/datasets", json={"name": "ds"})).json()["id"]
		await api.http.post(f"/api/v1/datasets/{dataset}/items", json={"messages": [{"role": "user", "content": "q"}], "expected": "a"})
		evaluator = (await api.http.post("/api/v1/evaluators", json={"name": "ev", "type": "exact", "config": {}})).json()["id"]
		base = {"dataset_id": dataset, "evaluator_id": evaluator, "candidate_model": "openai/gpt-4o-mini", "prompt_template_id": template["id"]}
		own = (await api.http.post("/api/v1/eval-runs", json=base)).json()["id"]
		await api.http.post(f"/api/v1/eval-runs/{own}/cancel")
		different = (await api.http.post("/api/v1/eval-runs", json={**base, "system_prompt": "Something else entirely."})).json()["id"]
	async with org_scoped_session(tenants.a) as db:
		runs = {str(r.id): r.prompt_fingerprint for r in await db.scalars(select(EvalRun))}
		stored = await db.get(PromptTemplate, uuid.UUID(template["id"]))
	assert runs[own] == fingerprint(stored) and runs[different] is None
