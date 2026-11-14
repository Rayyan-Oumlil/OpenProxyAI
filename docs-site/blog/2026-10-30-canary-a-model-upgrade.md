---
slug: canary-a-model-upgrade
image: /img/blog/og/canary-a-model-upgrade.png
title: "Canary a model upgrade: a slice of traffic, a dataset and a rollback"
tags: [product, engineering]
description: "Roll out a new model the way you roll out code. Score it on a dataset, send it a small share of live traffic, compare it side by side, and stop the experiment to roll back."
---

A new model version is cheaper, faster, or both. Switching every request at once is a bet. Switching a small share first is an experiment. OpenProxyAI lets you do the second without touching application code: your apps keep calling the same model name, and the gateway decides which model answers each request. If the numbers look wrong, you stop the experiment and traffic returns to the current model.

{/* truncate */}

![Apps call the gateway with the same model name. The gateway splits requests between the current model at 95 percent and a candidate at 5 percent, and a rollback stops the experiment so all traffic returns to the current model.](/img/blog/canary-a-model-upgrade.svg)

## Why a canary beats a switch

An all-at-once switch has three problems:

- **You learn from users.** The first signal of a worse answer is a complaint.
- **You cannot compare.** If everything changes on Tuesday, was the dip in satisfaction the model or the week?
- **Rollback means a deploy.** Changing the model name in code takes a release.

A canary fixes all three. A small share of requests goes to the candidate while the rest keeps going to the current model, both at the same time and in the same conditions. Differences you see are differences between the models.

## Step 1: clear the bar offline

Before any live traffic, run the candidate on a dataset of real examples. The earlier post on [testing a model change before you ship it](/blog/test-a-model-change-before-you-ship-it) covers the loop: captured traffic, a dataset, an evaluator, and an eval run with a cost cap. If you keep the dataset fresh, as in [this post on drift](/blog/keep-eval-datasets-fresh), the offline result means more.

Offline testing answers "is it broken?". It cannot answer "do users like it?", and it cannot show latency or cost at your real volume. That is what the canary is for.

## Step 2: split a slice of live traffic

Create an experiment in the console under Experiments, or through the API. You name the model your apps already call as the **target**, then list the **variants**:

| Variant | Weight | Role |
|---|---|---|
| The current model | 95 | Control. Most users see no change. |
| The candidate | 5 | The slice you are testing. |

Three details to get right:

- **List the current model as a variant too.** Weights are shares among the variants you list, so a lone candidate with a small weight would receive everything.
- **The choice is made per request.** Two messages from one user can land on different variants. That is fine for a stateless call and worth knowing for a chat.
- **Policy still applies.** If your organization uses a model allowlist, every variant must be on it when you create the experiment. If routing is enforced and a variant is not authorized for a request, the gateway skips the experiment for that request and serves the model the caller asked for. The canary never gets around your registry.

Only one experiment can be active per target model in an organization, so a canary on one model never fights another test.

## Step 3: watch it side by side

Open the experiment's results. Each variant has its own row, even when two variants use the same model with different settings:

- number of requests and average latency,
- total cost and tokens,
- the count of requests blocked by policy,
- your feedback scores, if your app sends ratings.

Policy blocks are worth watching. A candidate that triggers more refusals under your guardrails is not a drop-in replacement, whatever its benchmark says. Cost and latency come from real traffic, not a vendor page.

For the quality signal you need ratings. The application sends a thumbs up or down, or a named score, with the request id the gateway returned. The rating is attached to the variant that served that request. A test with no feedback shows cost and latency, but it cannot tell you which answers people preferred.

## Step 4: grow, hold, or roll back

| What you see | What to do |
|---|---|
| Latency, cost and ratings match or beat the control | Raise the candidate's weight and watch again. |
| Cost is better, ratings are slightly lower | Hold at the same share and gather more ratings. |
| Ratings fall, or policy blocks rise | Stop the experiment. |

**Rolling back is one action.** Stopping the experiment sends all requests to the target model again, from the next request. No deploy. Starting, stopping and every weight change are written to the admin audit log, so there is a record of who changed the split and when.

## Let the data steer: adaptive mode

If you would rather not nudge weights by hand, make the experiment adaptive. It judges by a feedback score such as thumbs, moves traffic toward the variant people rate higher, and never gives a variant less than a minimum share, so one that started badly can recover. It makes no decision until every variant has enough ratings, and it stops by itself when one variant is clearly better.

**A winner is recorded, not deployed.** Stopping ends the split and names the winner. Your production model does not change on its own. When you are ready, switch your apps or defaults to the winner yourself. Details are in [adaptive experiments](/guides/adaptive-experiments).

## A worked scenario

An illustrative case: a team wants to move a support assistant to a newer, cheaper model.

1. They run the candidate on a dataset built from last week's rated answers and see a pass rate close to the current model.
2. They create an experiment: current model at 95, candidate at 5.
3. After two days, the candidate's cost per request is lower and latency is similar. Ratings are close, but there are few of them.
4. They raise the candidate to 25. Ratings catch up, and policy blocks stay level.
5. They set the experiment to adaptive to settle it. The test records a winner. They update the model name in their apps and keep the audit log entries with the change ticket.

## Good to know

Ratings come from your application, and a small slice collects them slowly. Plan for a longer test at 5 percent than at 25. Changing the variants of a running test replaces them, and the ratings collected so far stop counting, so decide your variants before you start.

## What to do now

- Pick one model change you have been putting off.
- Run it on a dataset first, with a cost cap.
- Send thumbs ratings from your app.
- Start at a small share, list both models as variants, and write down your stop conditions before you begin.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker and no provider key. The console is at http://localhost:5173. Star the repo or open an issue if your rollout process needs something we do not cover yet.

## Sources

- Product docs: [Adaptive A/B experiments](/guides/adaptive-experiments), [Evaluating changes](/admin-console/evaluating-changes), [Feedback](/api-reference/feedback), [Audit logging](/security/audit-logging), [Policies and guardrails](/core-concepts/policies-and-guardrails).
- Related posts: [Test a model change on real examples before you ship it](/blog/test-a-model-change-before-you-ship-it), [Keep your eval dataset fresh](/blog/keep-eval-datasets-fresh).

These statements are based on OpenProxyAI's behavior at the post date.
