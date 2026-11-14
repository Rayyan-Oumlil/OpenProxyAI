---
slug: promote-prompts-through-a-quality-gate
title: "Promote prompts through a quality gate: no live edit without a passing eval"
tags: [product, engineering]
description: "Treat prompts like production code. Edits become drafts, a draft must pass an evaluation on your own dataset before it goes live, and every promotion or override is written to the audit log."
---

A prompt that applications call by name is production code. A one-line change to it can make every answer a little worse, and nobody notices until a customer does. In many companies, prompts are edited in a text box with no review, no test and no record. OpenProxyAI can put a quality gate in front of that text box: an edited prompt becomes a draft, the draft has to pass an evaluation on your own test cases, and only then does it replace the live version.

{/* truncate */}

![A prompt edit becomes a draft. The live version keeps serving. An evaluation run tests the draft on a dataset. If it passes, an admin promotes it. If it cannot pass, an admin can override with a written reason that is recorded.](/img/blog/promote-prompts-through-a-quality-gate.svg)

## Prompts as saved, versioned templates

First, the basics. A prompt template is a saved prompt that your applications call by its id, instead of carrying the text in their own code. Variables are filled in at call time. Every edit creates a new version rather than overwriting the old one, so you can always see what changed and compare behavior across versions.

That alone moves prompt wording out of application releases. The gate is what makes the move safe.

## What the gate does

The gate is a policy setting. It is off by default, and with it off, edits go live at once, as before. With it on:

1. **An edit makes a draft.** Editing the live prompt creates a new draft version. The live version keeps serving traffic. A new prompt also starts as a draft. A request cannot call a draft, so nothing untested reaches users by accident.
2. **You test the draft.** Start an evaluation run against a dataset of your own, using the draft's wording. The console's promote dialog links straight to this.
3. **An admin promotes it.** If the run passes, promotion makes the draft live and retires the version it replaced.

There is one draft per prompt at a time, so two people cannot promote competing edits at once. The system tells the second person to edit the existing draft or promote it first.

## What counts as passing

You decide how strict to be. You set the share of test items that must pass, and the minimum number of items a run must have scored, so a run of two cases cannot approve a prompt. A run counts only when all of this holds:

| Requirement | Why it exists |
|---|---|
| The run completed | A cancelled run, a failed one or one stopped by its spending cap never counts. |
| It tested this exact prompt | If the draft changes after the run, the run no longer counts, so approval cannot drift away from what actually ships. |
| It scored enough items | A tiny sample proves nothing. |
| The pass rate met your bar | The core test. |
| Few items were unscorable | Otherwise a run where most items errored could pass on the few that worked. |

At any time, anyone with developer access can ask where a draft stands. The answer lists the requirements, whether the draft passes, the best run so far and, if it does not pass, exactly what is missing. A refused promotion returns the same reasons, so there is no guessing.

## The override, with a paper trail

Sometimes a fix has to ship now. An admin can override the gate by giving a written reason. The reason is required, and the promotion is recorded in the audit log as an override, with the reason and what was unmet. In the console, an Override option appears in the promote dialog only when the gate is not satisfied.

This is the right balance. The gate is not an obstacle that people route around by copying the prompt into code. It is a guardrail with an escape hatch that leaves evidence. A reviewer can later list every override and ask whether it was justified.

Every normal promotion is in the audit log too, so you can answer who put which version live and when. See [an audit trail your auditor can read](/blog/an-audit-trail-your-auditor-can-read).

## A worked scenario

A support team has a prompt that drafts replies to customer emails. A teammate wants a friendlier tone.

1. They edit the prompt. It becomes version 5 as a draft, while version 4 keeps serving customers.
2. They start an evaluation run on a dataset of 80 past emails that the team already scored, using the draft's system message and a judge that checks for correct policy statements.
3. The first run passes the tone check but fails the pass-rate requirement: the friendlier wording makes the model promise refunds the policy does not allow. The status check names the gap.
4. They fix the wording and run again. This time the run completes, scores enough items and meets the bar.
5. An admin promotes version 5. Version 4 is retired. The audit log records the promotion with the run that vouched for it.

Without the gate, version 5 would have been live after step 1.

## Pairs well with the rest of evaluation

The same datasets and evaluators power other checks. You can [test a model change before you ship it](/blog/test-a-model-change-before-you-ship-it) against the same cases, and you can capture real traffic into a dataset from the console. The more your dataset looks like real work, the more the gate means. The [evaluating changes](/admin-console/evaluating-changes) guide walks through building one.

## What to do now

- [ ] Move prompts that matter into saved templates, so applications call them by id.
- [ ] Build a dataset of 30 to 100 real cases per important prompt, with expected answers or clear criteria.
- [ ] Choose an evaluator that fits: exact match, a pattern, or a judge with written criteria.
- [ ] Turn the gate on for production prompts, and set a pass rate and a minimum item count your team agrees with.
- [ ] Review overrides in the audit log every month.

## Good to know

The gate checks that a run of your dataset passed. It is only as good as the dataset and the evaluator, so keep adding real cases, especially the ones that went wrong once. The run tests the prompt's system message, so a template with no system message needs an override until it has one.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

This needs Docker and no provider key. The console is at http://localhost:5173. If it helps you, star the repo, and if your review process needs something we do not cover, open an issue.

## Sources

- [Prompts: playground and promotion](/guides/prompts): templates, versions, the promotion gate, what counts as a passing run and the override.
- [Evaluating changes](/admin-console/evaluating-changes): datasets, evaluators and runs in the console.
- [Adaptive experiments](/guides/adaptive-experiments): testing prompts and models on real traffic.
- [Test a model change before you ship it](/blog/test-a-model-change-before-you-ship-it): the same evaluation tools for models.
- [An audit trail your auditor can read](/blog/an-audit-trail-your-auditor-can-read): where promotions and overrides are recorded.

These statements are based on the sources above and on OpenProxyAI's behavior as of 2026-10-30.
