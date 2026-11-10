"""The prompt promotion gate (Phase 3, slice 6): when may a draft prompt template go live?

With the org's gate on, editing a template makes a draft. A draft is promoted only if an eval run vouches for it:

- the run **completed** (not cancelled, not stopped by its spending cap, not failed);
- it **tested this exact prompt**: the run recorded a fingerprint of the template's content, and that still matches, so
  editing the draft after its run means the run no longer counts;
- it **scored enough items** (``prompt_gate_min_items``), so a run of two cannot promote a prompt;
- the **pass rate** over scored items is at least ``prompt_gate_min_pass_rate``;
- no more than a tenth of its items **could not be scored**, so a run where most items errored out cannot pass on the few
  that happened to work.

An admin can override with a written reason; that is audited. The gate checks the template's system message, because that is
what a run varies: the dataset supplies each item's own messages. A template with no system message cannot be vouched for by
a run at all, and needs an override.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation import EvalRun
from app.models.prompt_template import PromptTemplate
from app.services.policy_service import PolicyConfig

MAX_UNSCORED_SHARE = 0.1


def fingerprint(template: PromptTemplate) -> str:
	"""A hash of everything about a template that shapes its output, so any edit changes it."""
	return hashlib.sha256(json.dumps([template.system_message, template.user_template], ensure_ascii=False).encode()).hexdigest()


@dataclass(frozen=True)
class RunSummary:
	run_id: uuid.UUID
	status: str
	total_items: int
	scored_items: int
	failed_items: int
	pass_rate: float | None
	mean_score: float | None

	def as_dict(self) -> dict:
		return {
			"run_id": str(self.run_id), "status": self.status, "total_items": self.total_items, "scored_items": self.scored_items,
			"failed_items": self.failed_items, "pass_rate": self.pass_rate, "mean_score": self.mean_score,
		}


@dataclass(frozen=True)
class GateResult:
	passed: bool
	qualifying: RunSummary | None  # the run that satisfied the gate
	best: RunSummary | None  # the run that came closest, to explain a refusal
	reasons: list[str]  # why it did not pass; empty when it did


def summarize(run: EvalRun) -> RunSummary:
	scored = run.completed_items - run.failed_items
	return RunSummary(
		run_id=run.id, status=run.status, total_items=run.total_items, scored_items=scored, failed_items=run.failed_items,
		pass_rate=run.passed_items / scored if scored else None, mean_score=float(run.score_sum) / scored if scored else None,
	)


def shortfalls(summary: RunSummary, policy: PolicyConfig) -> list[str]:
	"""Why this run does not satisfy the gate. Empty means it does."""
	reasons = []
	if summary.status != "completed":
		reasons.append(f"the run ended as {summary.status}, not completed")
	if summary.scored_items < policy.prompt_gate_min_items:
		reasons.append(f"only {summary.scored_items} items were scored; at least {policy.prompt_gate_min_items} are required")
	if summary.pass_rate is None or summary.pass_rate < policy.prompt_gate_min_pass_rate:
		shown = "n/a" if summary.pass_rate is None else f"{summary.pass_rate:.0%}"
		reasons.append(f"the pass rate was {shown}; at least {policy.prompt_gate_min_pass_rate:.0%} is required")
	if summary.total_items and summary.failed_items / summary.total_items > MAX_UNSCORED_SHARE:
		reasons.append(f"{summary.failed_items} of {summary.total_items} items could not be scored, more than {MAX_UNSCORED_SHARE:.0%}")
	return reasons


async def check_gate(db: AsyncSession, org_id: uuid.UUID, template: PromptTemplate, policy: PolicyConfig) -> GateResult:
	if not (template.system_message or "").strip():
		return GateResult(False, None, None, ["this template has no system message, so an eval run cannot test it"])
	runs = list(await db.scalars(
		select(EvalRun).where(
			EvalRun.org_id == org_id, EvalRun.prompt_template_id == template.id, EvalRun.prompt_fingerprint == fingerprint(template),
		).order_by(EvalRun.created_at.desc())
	))
	if not runs:
		return GateResult(False, None, None, ["no eval run has tested this exact prompt; run one with prompt_template_id set, after your last edit"])
	summaries = [summarize(r) for r in runs]
	for summary in summaries:
		if not shortfalls(summary, policy):
			return GateResult(True, summary, summary, [])
	completed = [s for s in summaries if s.status == "completed" and s.pass_rate is not None]
	best = max(completed, key=lambda s: s.pass_rate or 0.0) if completed else summaries[0]
	return GateResult(False, None, best, shortfalls(best, policy))
