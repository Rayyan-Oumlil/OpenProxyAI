---
slug: claude-opus-5-5-gateway-checklist
image: /img/blog/og/claude-opus-5-5-gateway-checklist.png
title: "Claude Opus 5.5 is out: a launch-day checklist for your gateway"
tags: [product, engineering]
description: "Anthropic released Claude Opus 5.5 on 22 September 2026 at lower prices. Here is how a platform team can add a new model safely: registry, data classes, a small canary, evaluation and budgets."
---

On 22 September 2026, Anthropic announced Claude Opus 5.5, the first model in its Claude 5.5 family. Anthropic says it costs 40 percent less to run than Opus 5 on typical workloads, with lower per-token prices. Every launch like this sets off the same internal debate: switch everyone today, or wait. A gateway turns that debate into a controlled rollout. This post covers what Anthropic announced and the five steps a platform team can follow, from registry entry to wider traffic.

{/* truncate */}

![Five steps from a model launch to rollout: announcement, registry entry with data class and region, canary share, evaluation on your own data, then budgets and wider traffic.](/img/blog/claude-opus-5-5-gateway-checklist.svg)

## What Anthropic announced

According to Anthropic's announcement page:

| Item | Detail |
|---|---|
| Model | Claude Opus 5.5, the first model in the new Claude 5.5 family |
| Date | 22 September 2026 |
| Price per million tokens | Input 4 dollars, output 20 dollars, cache reads 0.20 dollars. Anthropic lists Opus 5 at 5, 25 and 0.50 dollars |
| Cost on typical work | Anthropic says it costs 40 percent less than Opus 5 at default settings |
| Speed | Output more than 30 percent faster than Opus 5 |
| Fast mode | Available in Claude Code and the Claude Platform at 8 dollars input and 40 dollars output per million tokens |
| Safeguards | Deployed with safeguards similar to those on its most capable models, with verification programs for life sciences and cybersecurity use |
| Next | Anthropic says Claude Sonnet 5.5 and Claude Haiku 5.5 will follow in the coming weeks |

Those are vendor figures from Anthropic's page. Benchmarks and price claims describe Anthropic's own tests and typical workloads, so measure your own before you decide.

## Why a launch is an operations event

A new model is not only a quality change. It changes four things your platform team already owns.

1. **Cost.** Prices and caching behavior differ, so your budgets and forecasts change.
2. **Data rules.** A new model has its own retention terms, regions and risk profile. Whether your confidential data may reach it is a decision, not a default.
3. **Behavior.** Answers differ in length, tone and refusals. Prompts tuned for the last model may behave differently.
4. **Reliability.** A fresh model may have different limits and capacity on day one.

## The five steps, with OpenProxyAI

OpenProxyAI is an open-source, self-hosted gateway. Your applications call one OpenAI-compatible endpoint, so changing a model is a gateway decision, not a code change in each app.

**1. Add it to the registry.** The model registry lists the models you have approved. Each entry records the highest data class the model may receive, its regions, a risk rating and its retention terms, and an admin can enable or disable it. Add Opus 5.5 with the class and regions your security team agrees on. Until you do, enforced routing will not send it any traffic. See [Provider routing](/core-concepts/provider-routing).

**2. Set data classes first.** Decide the highest class the new model may handle. A common start is internal, then raise it after review. A request above that class is never sent to the model, and you can preview the effect in log-only mode before enforcing. See [Data residency](/security/data-residency).

**3. Run a canary.** An experiment splits traffic for a target model between variants by weight. Send a small share to Opus 5.5 and the rest to your current model. An adaptive experiment can also move traffic toward the variant people rate higher once enough feedback arrives, and it records a winner rather than switching for you. See [Adaptive experiments](/guides/adaptive-experiments).

**4. Evaluate on your own data.** Build a dataset from real traffic, with personal data kept out, pick an evaluator and run the new model against it with a cost cap. You see each item's answer and why it passed or failed. See [Evaluating changes](/admin-console/evaluating-changes).

**5. Check budgets, then widen.** Budgets and rate limits apply per organization, team and user, so a cheaper model that is used far more can still surprise you. If a new model has no price listed yet, the call still completes and its cost is flagged as an estimate. Watch spend during the canary, then raise the share. See [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets).

## A worked scenario

A platform team manages a support assistant on its current top model. On launch day it adds Opus 5.5 to the registry for the internal class only. It starts an experiment that sends a small share of support traffic to the new model. Over the week it collects thumbs ratings and runs an evaluation on a few hundred past tickets, with a cost cap. The results look good, so it raises the share, keeps the old model as the fallback, and revisits the data class for the customer-facing app after a security review. Nobody changed application code.

## Checklist for the next launch

- Add the model to the registry with an agreed data class, regions and risk rating.
- Keep it disabled for sensitive classes until security signs off.
- Start with a small canary and a clear feedback score.
- Run an evaluation on your own data with a cost cap.
- Compare spend and latency, then widen in steps.
- Keep the previous model available for a quick return.

## Good to know

Anthropic's announcement mentions Sonnet 5.5 and Haiku 5.5 as coming. Treat each model as its own registry entry and its own canary, because class, price and behavior differ.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If it helps, star the repo or open an issue with the rollout steps you want easier.

## Sources

- [Anthropic: Introducing Claude Opus 5.5](https://www.anthropic.com/news/claude-opus-5-5): date, pricing, speed, safeguards, upcoming models.
- Related: [Provider routing](/core-concepts/provider-routing), [Evaluating changes](/admin-console/evaluating-changes), [Adaptive experiments](/guides/adaptive-experiments), [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets).

These statements are based on Anthropic's announcement and on OpenProxyAI's behavior at the post date.
