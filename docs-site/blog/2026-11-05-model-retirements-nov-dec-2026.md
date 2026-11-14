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

You cannot migrate a caller you have not found. A gateway sees the model on every request, so ask it. In OpenProxyAI the request logs and analytics can be filtered by model, team and date range, which tells you volume, recency and cost for the model that is going away. That tells you where to look. Then ask the teams involved which application is behind it.

### 2. Treat the replacement as a new data-processing decision

A newer model is not just a newer version. Its provider may keep prompts for a different number of days, process them in different regions, or train on them under different terms. In the OpenProxyAI model registry, each model carries its own clearance: the most sensitive data class it may receive, its regions, risk rating, retention and whether it trains on data. Add the replacement as its own entry and fill those fields from the provider's current terms. Nothing is inherited from the old model, so a replacement is never quietly cleared for confidential data just because its predecessor was.

![The OpenProxyAI model registry listing five models. openai/gpt-5 shows as Disabled, while openai/gpt-6.1-sol, its replacement, is Enabled. Each row shows its provider key, maximum data class, regions, risk, retention and whether it trains on data.](/img/blog/console-model-registry.png)

### 3. Let callers ask for a job, not a model name

If the application sends a specific model name, every migration is a code change in every service. If it asks for a capability, such as code generation, the registry decides which vetted model does that job. Give the old and new models the same capability, and the switch becomes a registry edit with no change in the caller. The gateway picks the cheapest authorized model that has the capability, so register candidates deliberately.

### 4. Test the replacement on your own prompts before you cut over

A provider's benchmark does not know your prompts. Capture a share of real traffic, build a dataset from it, and run an eval with the candidate model and a cost cap. To compare under live traffic instead, an adaptive experiment moves traffic toward the variant your users rate better and stops when one is clearly ahead. See [Evaluating changes](/admin-console/evaluating-changes) and [adaptive experiments](/guides/adaptive-experiments).

### 5. Disable the old model, so its name fails clearly

Turn the old model off in the registry. In the demo stack, where the old and new models share the same capability, the effect is immediate. A capability request that was served by the old model is now served by the replacement, with no change in the caller, and the response tells you which model answered and why it was chosen.

A caller that still hard-codes the old name gets an immediate, readable refusal from the gateway instead of a provider error days later. The refusal is HTTP 446, the same status the gateway uses for every policy block, with a plain sentence such as "openai/gpt-5 is not available to your organization right now." It is recorded in the request log, so you find the stragglers on your schedule, not on the provider's.

## Good to know

Disabling a model refuses calls that name it rather than silently redirecting them. That is deliberate: a silent substitution would change how your data is handled without anyone deciding to. Put the provider dates in your own calendar, and run the eval in step 4 with the settings you actually send, since defaults for reasoning depth and output length move between model generations.

## Try it

The demo needs Docker and no provider key. A fake model stands in for the provider, so you can run the flow above at no cost.

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker and no provider key. The console is at http://localhost:5173. OpenProxyAI is open source (Apache-2.0) and runs in your own environment, so the registry, the logs and the keys stay with you. If it is useful, star the repo or open an issue.

## Sources

- [Anthropic: Model deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations), the Claude Sonnet 4.5 row and its November 30, 2026 retirement.
- [OpenAI: Deprecations](https://developers.openai.com/api/docs/deprecations), the December 11, 2026 shutdown rows for the GPT-5 and o3 families.
- [OpenAI Developer Community: upcoming model shutdowns in 2026](https://community.openai.com/t/deprecation-notice-upcoming-model-shutdowns-in-2026/1379553), the thread about the early notice email.
- OpenProxyAI docs: [Provider routing](/core-concepts/provider-routing), [Policies and guardrails](/core-concepts/policies-and-guardrails), [Request logs and analytics](/api-reference/analytics).

Checked against the providers' pages on November 13, 2026. Dates can move, so look again before you act. These statements are based on OpenProxyAI's behavior at the post date.
