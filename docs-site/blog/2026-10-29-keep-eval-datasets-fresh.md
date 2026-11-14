---
slug: keep-eval-datasets-fresh
image: /img/blog/og/keep-eval-datasets-fresh.png
title: "Offline evals look great, production got worse: keep your dataset fresh"
tags: [product, engineering]
description: "A test set written in spring says little about the questions users ask in autumn. Refresh datasets from recent traffic and ratings, score them the same way each time, and catch drift before your users do."
---

The eval run passes. The dashboard is green. Meanwhile, support tickets say the assistant got worse. The usual cause is not the model. It is the test set. A dataset written when the feature launched describes the questions you expected, not the ones people now ask. OpenProxyAI lets you rebuild a dataset from recent, rated traffic on a schedule, so the test keeps up with the product.

{/* truncate */}

![Captured sample flows into a rolling dataset of recent traffic, then into an eval run with the same scorer and a cost cap. A note advises keeping a frozen set and a rolling set.](/img/blog/keep-eval-datasets-fresh.svg)

## Why a good score can hide a bad week

An eval dataset is a snapshot. Real usage keeps moving:

- A new customer segment arrives and asks different things.
- A prompt change shifts which questions get long answers.
- A product launch adds vocabulary the old examples never used.
- People learn what the assistant is good at and ask for harder things.

If the dataset never changes, the pass rate measures how well you handle last season's questions. It can stay high while the experience drifts. The fix is not a bigger dataset. It is a dataset that is rebuilt from what is happening now.

## Build the set from real traffic

OpenProxyAI normally keeps only request metadata, not what users typed. You can opt in to **payload capture**, which keeps a redacted sample of prompts and answers. You choose the share of requests, it stores nothing until you do, and personal data is replaced before anything is written. Only answers that were delivered are kept, and requests above your data-class ceiling are never captured.

From that sample, an admin builds a **dataset** in the console under Evaluate, Datasets. An import can be filtered by:

| Filter | Use it to |
|---|---|
| Model | Test against the traffic one model actually served. |
| Date range | Take only the last week, so the set matches current behavior. |
| Feedback score | Keep answers users liked, or answers they disliked. |
| Random order | Get a spread across the period, not only the newest rows. |

Two details make a scheduled refresh safe. Importing the same requests twice adds nothing, so a weekly import with a moving start date only brings in what is new. And every row is scanned for personal data again on the way in, so a row that carries any is skipped, and the import reports how many it skipped and why.

You can also add items by hand, with an expected answer. That is the right place for the awkward cases support told you about, such as a refund question phrased as a complaint.

## Use ratings to pick what matters

If your application sends a thumbs or a score for each answer, those ratings travel with the captured request. That gives you two useful sets:

1. **Answers people liked.** A regression guard. A change should not break what already works.
2. **Answers people disliked.** A list of known problems. A change should improve these, and you can see by how much.

Ratings are sent with the request id the gateway returns on every response, so wiring this up is a small change in the app. The earlier post on [testing a model change on real examples](/blog/test-a-model-change-before-you-ship-it) walks through the full loop. This post is about what happens after the first run, when the dataset starts to age.

## Score it the same way every time

A trend is only meaningful if the ruler stays the same. Create an evaluator once (exact match, a pattern, or an LLM judge with criteria you write) and reuse it for every run. Then start an eval run: pick the dataset, the evaluator and the model to test, and set a cost cap.

Two behaviors help you read the result honestly:

- **Unscorable items are listed apart.** An item refused by policy, an upstream error, or an item with no expected answer is shown with its reason and left out of the pass rate. A few broken items do not drag a good result down, and you can still see them.
- **A run has a spending cap.** A run costs real money, one model call per item plus one for a judge. The cap stops it, and the table shows cost against the cap.

Check the count of items that could not be scored before you trust a number. A pass rate over fewer items than last time is a different measurement.

## A routine that works

| Cadence | What you do | What you learn |
|---|---|---|
| Once | Build a **frozen** dataset of a few hundred reviewed items. Never change it. | A stable baseline. A drop here means the model or prompt got worse. |
| Weekly | Import the last week of rated traffic into a **rolling** dataset. | Whether current questions are handled as well as old ones. |
| Weekly | Run the same evaluator on both sets with the current production model. | Two numbers. If frozen holds and rolling falls, usage moved. |
| Before a change | Run the candidate on both sets. | Whether it is better on today's traffic, not only on the old set. |
| Monthly | Delete stale items from the rolling set. | A set that stays about the size you can afford to run. |

The gap between the two numbers is the signal. If both drop, something regressed. If only the rolling set drops, your test set was telling you about a world that has changed.

## Good to know

- Captured rows expire with your plan's retention, but an imported dataset item is a copy that stays until you delete it. Decide what belongs in a dataset, and prune it.
- The most sensitive requests are never captured, and rows with personal data are skipped. A dataset built from capture therefore reflects less sensitive traffic. If your riskiest workflow is not in it, add hand-written items for it.
- An item you write by hand that contains personal data is refused with a reason, not quietly rewritten, because changing an expected answer would change what the test checks.

## What to do now

- Turn on capture at a low rate and send ratings from your app.
- Create one frozen dataset and one rolling dataset, and one evaluator you will not change.
- Schedule a weekly import and a weekly run, and write the two pass rates in the same place each time.
- Add the last three complaints from support as hand-written items.
- Before the next model or prompt change, run it on both sets.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker and no provider key. The console is at http://localhost:5173. If you star the repo or open an issue, tell us which dataset filters you wish existed.

## Sources

- Product docs: [Capturing traffic for evaluation](/guides/payload-capture), [Evaluating changes](/admin-console/evaluating-changes), [Datasets and imports](/api-reference/datasets), [Evaluators and eval runs](/api-reference/eval-runs), [Feedback](/api-reference/feedback).
- Related post: [Test a model change on real examples before you ship it](/blog/test-a-model-change-before-you-ship-it).

These statements are based on OpenProxyAI's behavior at the post date.
