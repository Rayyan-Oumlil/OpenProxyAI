---
slug: run-quality-checks-on-every-model-change
title: "Run quality checks on every model change, like any other release"
tags: [product, engineering]
description: "Make model and prompt changes a routine release check: keep a saved test set, score every candidate with the same evaluator, compare pass rate and cost, and gate prompts until they pass."
---

You would not ship code without running the tests. Yet models and prompts change all the time, and many teams swap them on instinct. A cheaper model arrives, a prompt gets a tweak, a provider retires a version, and the change goes out with a quick manual try. The fix is not a bigger project. It is a habit: keep a saved test set, and run it on every change. OpenProxyAI gives you the pieces in the console.

{/* truncate */}

![A repeating loop: something changes, such as a model or a prompt, you run your saved test set, you compare pass rate and cost, and you decide whether to ship or keep the old one.](/img/blog/run-quality-checks-on-every-model-change.svg)

## Why a routine beats a project

If you already know how to [test a model change before you ship it](/blog/test-a-model-change-before-you-ship-it), the next step is making it boring. A one-off evaluation tells you about one decision. A routine tells you about every decision, and it makes regressions visible while they are small.

Three things make a routine work:

- **A stable test set.** If the questions change every time, the scores cannot be compared.
- **The same scoring rule.** Change the evaluator and you change the meaning of the number.
- **A written bar.** Your team agrees what pass rate and cost are good enough before the run, not after.

## Build your test set once

OpenProxyAI keeps test sets as datasets. You can fill one in two ways, and most teams use both.

1. **Import real traffic.** If you turned on sampled capture, you can import captured requests into a dataset and filter by model, date or feedback score. Importing only answers people rated well is a good way to build a set of examples that matter. Personal data is replaced before capture, and rows that still contain personal data are never imported. Importing the same requests twice adds nothing, so it is safe to refresh the set.
2. **Write items by hand.** Add the hard cases that real traffic does not cover yet, with an expected answer. An item you write that contains personal data is refused with a reason, instead of being quietly rewritten, because changing an expected answer would change what the test checks.

Keep the dataset small enough to run often and varied enough to catch surprises. Add an item every time a user finds a failure, so the set grows from real problems.

## Pick a scoring rule and keep it

An evaluator says how an answer is scored. There are three kinds:

| Evaluator | Good for |
|---|---|
| Exact match | Classification, extraction, short fixed answers |
| Pattern match | Answers that must contain or follow a format |
| Model judge | Open-ended answers, graded against criteria you write |

A judge call is an ordinary gateway call, so your policy applies to it and it is metered and logged like any other. If the judge is refused or replies with something that is not a clean score, that item shows up as an error, never as a quiet zero. Write criteria that describe a good answer in plain words, then leave them alone, so scores stay comparable from one run to the next.

## Run it on every change

A run takes a dataset, an evaluator and the model to test, and optionally a system prompt or a saved prompt template. You set a cost cap before it starts, because a run makes real model calls: one per item, plus one per item for a judge. When the cap is reached, the run stops and is marked that way. The console page updates while it works, and you can cancel it.

Good moments to run it:

| Trigger | Question the run answers |
|---|---|
| A cheaper model is announced | Does it hold your pass rate at a lower cost? |
| A prompt is edited | Did the change help or break old cases? |
| A provider retires a model | Is the replacement good enough? See [model retirements Nov 30 to Dec 11](/blog/model-retirements-nov-30-dec-11) |
| A policy or guardrail changes | Do legitimate requests still pass and still read well? |

Run the current model too, so you compare against a fresh baseline from the same day, not an old number.

## Read the result the right way

Open a run to see each item's answer and why it passed or failed. The headline is a pass rate and an average score, plus the cost against the cap. Two details make the number trustworthy.

- **Items that could not be scored are listed separately.** If an item was refused by policy, hit a provider error, or had no expected answer, it is left out of the pass rate and shown with its reason. A few broken items do not drag a good result down, and you can still see them.
- **Check the error count before you trust the score.** If a lot of items could not be scored, fix the cause, then run again.

Write down three numbers per run: pass rate, cost, and the count of unscored items. A small table in your team wiki is enough to turn a one-off check into a history.

## Make prompts pass a gate

For prompts, you can turn the logic into a rule. With the promotion gate on, a prompt that was edited becomes a draft, and promoting it needs a completed run of that exact prompt that scored enough items at the required pass rate. If it is not ready, you can start the run from the same dialog. An admin can override with a written reason, which goes into the audit log. That means a prompt change cannot reach production on enthusiasm alone, and an exception leaves a trail.

## After the check, learn from live traffic

An offline score is a strong signal, not the last word. When a candidate passes, you can run an adaptive experiment on a slice of live traffic. It moves traffic toward the variant people rate higher and stops by itself when one is clearly better. The winner is recorded, and nothing is switched on for you. You decide when to change the target.

## What to do now

- Turn on sampled capture in a non-critical setting, and have your app send thumbs or scores with the request id.
- Create one dataset from rated traffic and add ten hand-written hard cases.
- Create one evaluator and keep its settings fixed.
- Run your current model first, record the numbers, and agree on the bar for a new candidate.
- Add the run to your release checklist next to unit tests.
- Turn on the prompt promotion gate if prompts change often.

## Good to know

A run spends real money, so set a cost cap that suits the size of your dataset. Scores from a model judge depend on your criteria, so keep them stable, and spot-check a few judged answers by hand.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

It needs Docker and no provider key. The console is at http://localhost:5173. Star the repo or open an issue if you want an evaluation feature we do not have yet.

## Sources

- [Evaluating changes](/admin-console/evaluating-changes): the console loop for capture, datasets, evaluators and runs.
- [Adaptive experiments](/guides/adaptive-experiments): live traffic splits with a recorded winner.
- [Prompts](/guides/prompts): templates and the promotion gate.
- [Payload capture](/guides/payload-capture): sampled, redacted capture of delivered traffic.
- [Test a model change before you ship it](/blog/test-a-model-change-before-you-ship-it): the one-off version of this loop.

These statements are based on the OpenProxyAI documentation and the product's behavior at the post date.
