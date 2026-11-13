---
slug: model-retirements-nov-30-dec-11
title: "Two model retirements in 28 days: what to do before November 30 and December 11"
tags: [engineering, product]
description: Claude Sonnet 4.5 retires on November 30 and OpenAI's GPT-5 and o3 families shut down on December 11. A plan to find who still calls them, move to a replacement safely, and make the old name fail loudly instead of at 3 a.m.
---

Two provider deadlines land inside four weeks. Anthropic retires Claude Sonnet 4.5 on **November 30, 2026**. OpenAI shuts down the GPT-5 and o3 families on **December 11, 2026**. After each date, a request that names the old model fails. The models themselves are not the risk. The risk is the one service nobody remembers, with the model name hard-coded, that starts returning errors on a Monday morning.

{/* truncate */}

![A timeline from November 13 to December 11 with two marked dates: Claude Sonnet 4.5 retires on November 30, and the GPT-5 and o3 families shut down on December 11.](/img/blog/retirement-timeline.svg)

## What is retiring, from the providers' own pages

| Provider | Model IDs | Retires | Named replacement |
|---|---|---|---|
| Anthropic | `claude-sonnet-4-5-20250929` | November 30, 2026 (deprecated September 30) | `claude-sonnet-5-5` |
| OpenAI | `gpt-5`, `gpt-5-mini`, `gpt-5-nano`, `gpt-5-pro`, `o3`, `o3-pro` and their dated snapshots | December 11, 2026 (notice June 11) | `gpt-6.1-sol` for `gpt-5` and `o3`, `gpt-6.1-terra` for mini, `gpt-6-luna` for nano |

Two cautions before you plan around these dates.

- **Cloud resellers keep their own calendar.** Anthropic's page says its dates apply to Anthropic-operated platforms. Amazon Bedrock and Google Cloud set their own retirement schedules for the same models, so check them separately if that is how you reach the model.
- **Use the official page, not an email.** A thread on OpenAI's developer forum reports an early notice email that listed a different date and different replacements, followed by a correction. The deprecations page and the `shutdown_date` field on OpenAI's list-models endpoint are the sources to trust.

## The plan, in five steps

### 1. Find who still calls the old model

You cannot migrate a caller you have not found. The gateway already records the model on every request, so ask it:

```bash
curl -H "Authorization: Bearer $ADMIN_JWT" \
  "https://gateway.your-company.com/api/v1/analytics/logs?model=anthropic/claude-sonnet-4-5-20250929&start_date=2026-10-01&page_size=50"
```

The endpoint also takes a `team_id` and a date range. The result tells you volume, recency and cost for that model. It does not name the application, so use it to decide where to look, then ask the teams involved. (The console's request-log page filters by status, policy action, reason, session and date, not by model, so this one is an API call.)

### 2. Treat the replacement as a new data-processing decision

A newer model is not just a newer version. Its provider may keep prompts for a different number of days, process them in different regions, or train on them under different terms. In the model registry, each model carries its own clearance: the most sensitive data class it may receive, its regions, risk rating, retention and whether it trains on data. Add the replacement as its own row and set those fields from the provider's current terms. Nothing is inherited from the old model, so a replacement is never quietly cleared for confidential data just because its predecessor was.

![The OpenProxyAI model registry listing five models. openai/gpt-5 shows as Disabled, while openai/gpt-6.1-sol, its replacement, is Enabled. Each row shows its provider key, maximum data class, regions, risk, retention and whether it trains on data.](/img/blog/console-model-registry.png)

### 3. Let callers ask for a job, not a model name

If the application sends `model: "openai/gpt-5"`, every migration is a code change in every service. If it sends `model: "cap:CODE"`, the registry decides which vetted model does that job. Give the old and new models the same capability tag, and the switch is a registry edit. This needs the organization's routing mode set to `enforce`, and it chooses the cheapest authorized model with the capability, so register candidates deliberately.

### 4. Test the replacement on your own prompts before you cut over

A provider's benchmark does not know your prompts. Capture a share of real traffic, build a dataset from it, and run an eval with the candidate model and a cost cap. To compare under live traffic instead, an adaptive experiment moves traffic toward the variant your users rate better and stops when one is clearly ahead. See [Evaluating changes](/admin-console/evaluating-changes) and [adaptive experiments](/guides/adaptive-experiments).

### 5. Disable the old model, so its name fails clearly

Turn the old model off in the registry. Here is the real output from the demo stack, where `openai/gpt-5` and `openai/gpt-6.1-sol` share the `CODE` capability.

Before, a capability request is served by the old model:

```text
model=cap:CODE -> HTTP 200
  x-openproxyai-model: openai/gpt-5
  x-openproxyai-route-reason: capability
```

After disabling `openai/gpt-5` in the registry, the same request, with no change in the caller, is served by the replacement:

```text
model=cap:CODE -> HTTP 200
  x-openproxyai-model: openai/gpt-6.1-sol
  x-openproxyai-route-reason: capability
```

A caller that still hard-codes the old name gets an immediate, readable refusal from the gateway, not a provider error days later:

```json
{
  "error": "routing_blocked",
  "reason_code": "no_authorized_model",
  "detail": "No model authorized for this request's data class can serve it.",
  "explanation": "openai/gpt-5 is not available to your organization right now.",
  "route_reason": "not_authorized:disabled",
  "data_class": "internal",
  "requested_model": "openai/gpt-5"
}
```

That is HTTP 446, the same status the gateway uses for every policy block, and it is recorded in the request log. You find the stragglers on your schedule, not on the provider's.

## What this does not do

- **It does not redirect a hard-coded name.** Disabling `openai/gpt-5` does not send `openai/gpt-5` traffic to its replacement. It refuses it. That is deliberate, because a silent substitution changes data handling without anyone deciding to. The cost is that a missed caller breaks, loudly, which is why step 1 comes first.
- **It does not learn about deprecations for you.** The registry holds what your team enters. Subscribe to the provider pages below and put the dates in your own calendar.
- **Capability routing needs routing enforcement.** If your organization runs routing in `off` or `log_only`, `cap:` requests are not accepted.
- **Behavior differs between model generations.** Defaults for reasoning depth, output length and refusals move. Run the eval in step 4 on the settings you actually send.

## Try the whole flow in a few minutes

The demo needs Docker and no provider key. A fake model stands in for the provider, so you can run every step above at no cost.

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Open http://localhost:5173 and sign in with the public demo login in the README. OpenProxyAI is open source (Apache-2.0) and runs in your own environment, so the registry, the logs and the keys stay with you.

## Sources

- [Anthropic: Model deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations), the Claude Sonnet 4.5 row and its November 30, 2026 retirement.
- [OpenAI: Deprecations](https://developers.openai.com/api/docs/deprecations), the December 11, 2026 shutdown rows for the GPT-5 and o3 families.
- [OpenAI Developer Community: upcoming model shutdowns in 2026](https://community.openai.com/t/deprecation-notice-upcoming-model-shutdowns-in-2026/1379553), the thread about the early notice email.
- OpenProxyAI docs: [Provider routing](/core-concepts/provider-routing), [Policies and guardrails](/core-concepts/policies-and-guardrails), [Request logs and analytics](/api-reference/analytics).

Checked against the providers' pages on November 13, 2026. Dates can move, so look again before you act.
