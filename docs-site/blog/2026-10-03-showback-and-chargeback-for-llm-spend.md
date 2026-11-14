---
slug: showback-and-chargeback-for-llm-spend
image: /img/blog/og/showback-and-chargeback-for-llm-spend.png
title: "Showback and chargeback for LLM spend: label every request, report by team"
tags: [product, engineering]
description: "Turn one shared AI invoice into a per-team report. Tag requests with labels, tie keys and users to teams, set monthly budgets, and pull spend by team, user, key and model for finance."
---

The provider invoice says you spent a lot on AI last month. Finance wants to know which department owes what. Engineering shares two provider keys across six services and has no way to split the number. This is the usual starting point, and it is fixable without asking every team to change how it works. Because every request already passes through the gateway, each one can carry a team, a user, a key and a few labels of your choosing. That is all showback and chargeback need.

{/* truncate */}

![Requests carry a team, a user, a key and labels. The gateway records cost for each. Finance reads spend by team at month end, and budgets stop a team that goes over.](/img/blog/showback-and-chargeback-for-llm-spend.svg)

## Showback and chargeback in one minute

**Showback** means showing each team what it spent, with no money moving. **Chargeback** means billing that spend to the team's budget or cost center. Most companies start with showback, because it changes behavior on its own: once a team sees its own number, it asks why that summarizer uses the biggest model.

Both need the same thing: spend that is attributed at the moment of the request, not guessed afterward from a shared invoice. Reconstructing attribution later from key names and Slack threads is slow and never fully accurate.

## Four things every request can carry

| Attribution | How it gets attached | What it answers |
|---|---|---|
| Team | The key is tied to a team, or the caller sends a team header | Which department spent this |
| User | The person who owns the key | Who to talk to |
| Key | The API key used | Which application or service |
| Labels | A small JSON object in a request header | Anything else you care about: project, environment, feature, customer tier |

The team and the key do most of the work. Create one key per application and tie it to the owning team, and attribution needs no code change at all. A key that is tied to a team counts against that team's budget automatically. A shared key can still pick a team per call.

Labels are for the dimensions that teams and keys cannot express. Because they are plain tags on the request, they work with any OpenAI SDK through an extra header:

```http
x-openproxy-labels: {"app": "support-summarizer", "env": "prod"}
```

Agree on a short naming convention and write it down. Two spellings of the same project, such as `support-bot` and `supportbot`, split a number that should be one.

## Budgets turn a report into a control

Showback tells you what happened. A budget limits what can happen next. Each team can have a monthly dollar budget, each user a daily one, and the organization an overall one. A request that would go past a budget is refused with a clear message that names which limit was reached, so the caller knows whether to wait or ask for more.

When daily spend reaches 80 percent of the organization budget, the gateway sends a signed webhook with the spend, the budget and the percent used. Point it at the channel your platform team already watches, and nobody learns about an overrun from the invoice. For how the limits behave in more detail, see the [budgets reference](/core-concepts/rate-limiting-and-budgets).

## Pulling the month-end report

Everything below reads from the same request log, so the numbers agree with each other.

| You want | Where to get it |
|---|---|
| Spend, volume and latency by team, user, key and model, over a period you choose | The analytics overview, in the console or through the analytics API |
| A forecast of where the month will end | The overview includes a projected month-end figure, and the console shows a burn-down |
| Every request for one label value | The request log, filtered by label key and value |
| A custom cut, such as cost per model for one key this week | The structured query endpoint, for admins |
| Proof for an auditor that budgets and actuals line up | The compliance export, which includes budget versus actual |
| A check that the gateway counted what the provider billed | The reconciliation endpoint, which compares gateway usage with a provider export and shows every difference |

The last row matters for chargeback. If you are going to bill a team, you want to be able to show that the gateway's numbers match the provider's. Upload the provider's usage export, and the report shows any day and model where requests or tokens differ.

## A worked scenario

A company runs three AI features: a support summarizer, a contract search, and an internal coding helper. Before the gateway, one provider key served all three.

1. Platform creates a team for each owning department and one key per feature, each tied to its team.
2. Each application sends a label with its name and environment. Nothing else in the code changes.
3. Each team gets a monthly budget that finance approved. The organization gets an overall budget and the 80 percent webhook goes to the platform channel.
4. In the first week, the overview shows that the coding helper accounts for most of the spend and most of it is one large model. The team switches simple completions to a cheaper model and the daily line drops.
5. At month end, finance reads spend by team from the overview, checks it against the provider export with reconciliation, and books the charge.

Nobody had to estimate, and nobody had to join logs by hand.

## What to do now

- [ ] List your AI applications and the team that owns each.
- [ ] Create one key per application, tied to its team.
- [ ] Pick two or three label keys (for example `app` and `env`) and document the allowed values.
- [ ] Set a monthly budget per team and an organization budget.
- [ ] Add a webhook for the 80 percent alert.
- [ ] Schedule a monthly reconciliation against each provider's usage export.

## Good to know

Labels are recorded on each request and you can filter the request log by them. The by-team, by-user, by-key and by-model breakdowns come from the analytics overview, so treat teams and keys as your main cost dimensions and labels as the finer detail you drill into.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

This needs Docker and no provider key. The console is at http://localhost:5173. If it helps you, star the repo, and if something is missing for your reporting, open an issue.

## Sources

- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets): which limits exist, how a refusal is reported, how team attribution works.
- [Analytics API](/api-reference/analytics): the overview, request log filters, exports, reconciliation and structured query.
- [Chat completions](/api-reference/chat-completions): the label and team headers.
- [Webhooks](/guides/webhooks): the 80 percent budget alert.
- [Why your AI bill is unpredictable](/blog/why-your-ai-bill-is-unpredictable): the cost problem this fixes.

These statements are based on the sources above and on OpenProxyAI's behavior as of 2026-10-03.
