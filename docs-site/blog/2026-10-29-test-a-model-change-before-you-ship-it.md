---
slug: test-a-model-change-before-you-ship-it
image: /img/blog/og/test-a-model-change-before-you-ship-it.png
title: "Test a model change on real examples before you ship it"
tags: [product, engineering]
description: "Use captured traffic, datasets, scored eval runs and adaptive experiments to find out whether a new model or prompt is better, with a cost cap and a recorded winner you choose to apply."
---

A new model is announced, the price is lower, and someone says it is "basically the same". Is it? Most teams find out from users. OpenProxyAI lets you find out first: score the candidate on real examples, then run a live experiment on a slice of traffic, and decide with numbers. Nothing switches until you say so.

{/* truncate */}

![Four steps: examples from a redacted sample of real traffic, an eval run that scores answers with a cost cap, an experiment that splits live traffic, and you decide because the winner is recorded and not applied automatically.](/img/blog/test-a-model-change-before-you-ship-it.svg)

## The problem

Benchmarks describe average models on average tasks. Your product has its own prompts, its own tone and its own edge cases. A model that wins a public leaderboard can still be worse at your support replies. And a model swap mid-product is hard to undo once users have noticed.

You want two kinds of evidence: does the new model pass your own tests, and do real users rate it as well as the old one?

## The loop

The console's Evaluate group walks through it in order. The same steps are available through the API.

1. **Capture traffic (opt-in).** Choose the share of delivered requests to keep. It is off until you turn it on. Personal data is replaced before anything is stored, and refused or failed requests are never kept.
2. **Collect feedback.** Your application sends a thumbs or a score for an answer, using the request id the gateway returns.
3. **Build a dataset.** Import captured traffic, filtered by model, date or feedback score, or write items by hand with an expected answer. Rows with personal data are never imported.
4. **Create an evaluator.** Pick exact match, a pattern match, or an LLM judge that grades answers against criteria you write.
5. **Start an eval run.** Choose the dataset, the evaluator and the candidate model, and set a cost cap. The page updates as it runs and you can cancel.
6. **Read the result.** See each item's answer and why it passed or failed. Items that could not be scored, for example because policy refused them, are listed apart and left out of the pass rate rather than counted as failures.

An eval run spends real money, one model call per item plus one per item for a judge. The cost cap stops it, and a run that hit the cap is marked that way.

## Then test it on live traffic

Offline tests tell you the candidate is not broken. An experiment tells you whether users prefer it.

An experiment splits the traffic for one model between variants, for example the current model and the candidate. You can keep a fixed split, or make it **adaptive**:

- It reads the ratings your application sends.
- It moves traffic toward the variant people rate higher.
- It makes no decision until every variant has a minimum number of ratings, so early noise does not steer it.
- It stops by itself when one variant is clearly better, and records the winner.

**The winner is recorded, not deployed.** Requests go back to your target model when the test ends. You read the results, and you decide whether to switch. An experiment never changes which model serves production on its own.

The results view shows each variant's traffic share, its chance of being the best one, and how many ratings are still needed. Every change to the split is written to the admin audit log.

## A worked scenario

A team wants to move a summarization feature to a cheaper model.

| Step | What they do | What they learn |
|---|---|---|
| 1 | Turn on capture at a low rate for two weeks. | A realistic sample of summaries, redacted. |
| 2 | Build a dataset from answers users liked. Add an LLM judge scoring for completeness. | A baseline pass rate for the current model. |
| 3 | Run the candidate on the same dataset with a cost cap. | The candidate passes most items but misses long documents. |
| 4 | Fix the prompt, run again. | The pass rate is close to the baseline. |
| 5 | Start an adaptive experiment with a thumbs rating. | Traffic moves toward whichever model users rate higher. |
| 6 | Read the recorded winner and the results. | Switch with evidence, or keep the current model. |

The same flow works for a prompt change. With the promotion gate turned on, a prompt edited as a draft can be promoted only after a completed eval run of that exact prompt scores well enough. An admin can override with a written reason, which is recorded in the audit log.

## What to do now

1. Turn on capture at a small sample rate for your most important feature.
2. Add a thumbs button, or any rating, and send it with the request id.
3. Build one dataset and one evaluator. Start with exact match or a pattern where the answer is checkable.
4. Run the current model first, to set a baseline, then the candidate.
5. Use an experiment before you move real traffic, and set a metric before you start.
6. Keep the winner's results with the change ticket.

## Good to know

Ratings come from your application, so an experiment with no feedback never moves. Only one active experiment is allowed per target model, and changing the variants of a running test resets the ratings collected so far. If you want fewer false winners when two models are nearly equal, ask for more ratings before a decision. See [Adaptive experiments](/guides/adaptive-experiments).

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If it helps, star the repo or open an issue.

## Sources

- OpenProxyAI docs: [Evaluating changes](/admin-console/evaluating-changes), [Adaptive experiments](/guides/adaptive-experiments), [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets).
- On this blog: [Switching models mid-conversation](/blog/switching-models-mid-conversation).

These statements are based on OpenProxyAI's behavior and docs as of October 29, 2026.
