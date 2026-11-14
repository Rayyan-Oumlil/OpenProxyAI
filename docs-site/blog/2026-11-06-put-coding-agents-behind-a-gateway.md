---
slug: put-coding-agents-behind-a-gateway
title: "Put your coding agents behind a gateway: budgets, visibility and policy"
tags: [product, security]
description: "Coding assistants in the IDE and the terminal send your code to a model all day. Point them at one OpenAI-compatible endpoint to get per-team budgets, a usage log and policy, without changing the tool."
---

Coding assistants are the fastest-spreading AI tool in most engineering teams. Each developer has a key, a plan or a personal account, and nobody can answer simple questions. How much are we spending? Which models see our code? Did someone paste a secret into a prompt? A gateway answers these by sitting between the tool and the model. If your coding tool lets you set a custom OpenAI-compatible base URL, putting it behind OpenProxyAI is a settings change.

{/* truncate */}

![An IDE assistant and a CLI coding agent both send requests to the OpenProxyAI endpoint, which applies budgets, visibility and policy before forwarding to model providers.](/img/blog/put-coding-agents-behind-a-gateway.svg)

## The problem

Three things go wrong when every developer connects a coding tool straight to a provider:

- **Spend is invisible and uneven.** One long agent session can cost more than a team's weekly budget, and you see it on the invoice.
- **There is no record.** When something odd happens, there is nothing to look at.
- **Everything is allowed.** The tool will send whatever is in the prompt, including keys and customer data pasted in for debugging.

## What a gateway changes

OpenProxyAI exposes an OpenAI-compatible API: chat completions, embeddings and models. The documentation describes switching an application that uses the OpenAI SDK as a change of the base URL and the key, not a rewrite. A tool that speaks the same API and lets you set its base URL and key can use the same path.

Check one thing first: whether the tool lets you override the base URL and key, and which API shape it speaks. We only describe the OpenAI-compatible endpoint. Look at your tool's own documentation for how to set those two values.

The setup has three steps:

1. In the admin console, create an API key for the developer or the team. Tie it to a team so that the team's budget applies.
2. In the tool, set the base URL to your gateway's `/v1` address and the key to the new key.
3. Pick a model name that your gateway serves. Any provider behind the gateway can be reached with the same OpenAI-shaped request.

Developers keep their editor, their shortcuts and their workflow.

## What you get

| Need | What the gateway does |
|---|---|
| Control spend | Requests, tokens and dollars per minute and per day, at the organization, user and team level. Team monthly budgets. A refusal names the limit that was reached. |
| See usage | Every request is logged with the model, the cost and the policy decision. Filter by team or by label. The console shows spend and a monthly projection. |
| Alert early | An alert webhook is sent when daily spend reaches 80 percent of the organization budget. |
| Keep secrets out | Policy can block personal data and your own blocked words, for example the prefix of an internal key format, before the prompt leaves your network. |
| Limit models | A model allow list, so only the models you approve are reachable. |
| Keep provider keys private | Developers hold gateway keys. Provider keys stay on the gateway, and a leaked developer key can be revoked on the next call. |
| Switch providers | Change the model behind a name or add a provider without touching any laptop. |

You can also send an optional label header with each request, for example the name of the tool or the project. The label is recorded on the request log and can be filtered there.

## A worked scenario

A platform team has 40 developers using an IDE assistant and a terminal agent.

1. They create one key per team, each with a daily dollar budget and a team monthly budget.
2. Policy starts in log-only mode, with personal data detection and a blocked word list that holds the prefixes of their internal key formats.
3. After a week they read the policy hits. One developer pasted a production token into a prompt. In log-only mode it was recorded. They switch to enforce mode for that check.
4. A refactoring agent loops one evening. It reaches the team's daily budget and gets a `429` that names the budget. The next morning the log shows which key and which model, and the budget resets at midnight UTC.
5. The security lead exports the log for the quarterly review.

## What to do now

- Ask which coding tools are in use and whether each allows a custom base URL and key.
- Create a key per team, with a budget, instead of a shared key.
- Start policy in log-only mode, and add your internal secret prefixes to the blocked words.
- Allow only the models you want developers to use.
- Watch the spend page for two weeks, then tune the budgets.
- Share the gateway address and a short how-to with the team.

## Good to know

Policy checks run on the prompt text, so keep blocked word lists specific. Streamed requests are checked against the remaining daily budget before they start, so a long streamed session near the limit can get a `402` at the start of a request.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker and no provider key. The console is at http://localhost:5173. If it helps, star the repo or open an issue naming the tool you want to connect.

## Sources

- OpenProxyAI docs: [Quickstart](/getting-started/quickstart), [Authentication](/getting-started/authentication), [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets), [Policies and guardrails](/core-concepts/policies-and-guardrails), [Audit logging](/security/audit-logging), [Webhooks](/guides/webhooks).

Statements are based on OpenProxyAI's documented behavior at the post date. We have not tested any specific coding tool, so check your tool's documentation for custom endpoint support.
