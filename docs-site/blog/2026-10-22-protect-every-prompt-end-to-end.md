---
slug: protect-every-prompt-end-to-end
title: "Follow one prompt through OpenProxyAI: seven checkpoints before and after the model"
tags: [security, product]
description: "What happens between your app and the model? A plain-words walk through one request: key, limits, policy, cache, routing, response checks and the audit log, with what each stage can stop."
---

Your app sends a prompt to a model. Between those two points, a lot can go wrong: an unknown caller, a runaway loop, an email address in the text, a model that should never see that data, an answer that leaks something. OpenProxyAI puts seven checkpoints on that path, in a fixed order, so every request gets the same treatment. This post follows one request from start to finish and says what each stop does for you.

{/* truncate */}

![Seven stages listed top to bottom: key, limits, policy, cache, route, response, audit, each with a one-line description of what it checks.](/img/blog/protect-every-prompt-end-to-end.svg)

## The request we will follow

A support tool sends this to the gateway: "Summarize this ticket for the customer", with the ticket text attached. The ticket includes a customer's email address and a card number that someone pasted by mistake. The tool uses the standard OpenAI client with its base URL pointed at the gateway.

## 1. Key: who is calling?

Every request carries a bearer API key. The gateway checks it on every call and finds the organization, and the team if the key is tied to one. A missing, revoked or expired key is refused with `401` before anything else runs. Keys are stored as hashes and shown once, so a database leak does not hand out working keys. See [Authentication](/getting-started/authentication) and [A leaked key should be a nuisance](/blog/a-leaked-key-should-be-a-nuisance).

## 2. Limits: is this allowed right now?

Requests per minute, tokens per minute and dollars per day are checked together, at the organization, user and team level. The first limit reached refuses the request with `429` and says which one, so the caller can react. A streamed request that would blow through the daily budget gets a `402` before it starts. See [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets) and [Budgets that fail closed](/blog/budgets-that-fail-closed).

## 3. Policy: is this content allowed?

The organization's policy looks at the request in order: is the model on the allow list, does the text contain a blocked keyword, does it contain personal data, does it look like a prompt injection. You pick a mode for the whole policy:

| Mode | What a hit does |
|---|---|
| Off | Nothing is checked. |
| Log only | The hit is recorded and the request goes through. Use it to see false positives first. |
| Enforce | The request is refused with `446` and a plain sentence that explains why. |

In our example, the card number is personal data. In enforce mode the request is refused, and the app gets a sentence it can show: what was refused and why, without revealing the rule that fired. The ticket never reaches a model. See [Policies and guardrails](/core-concepts/policies-and-guardrails) and [Refusals should explain themselves](/blog/refusals-should-explain-themselves).

## 4. Cache: have we answered this before?

If you enable caching, a request that matches a stored answer returns at once. No provider call, no provider cost. Policy runs first, so a request that policy blocks is never stored. The cache is scoped to the organization, and see [Caching](/core-concepts/caching) for the tiers.

## 5. Route: which model, which key?

On a miss, the request goes to a provider key for the model you asked for. Traffic is spread across your keys by weight, and the router moves it to healthy keys when one is rate-limited or failing, so your app sees one successful reply. If you use data classes, routing sends the request only to models cleared for that class of data, and refuses it otherwise. See [Provider routing](/core-concepts/provider-routing).

## 6. Response: is the answer safe to return?

You can turn on response checks. An answer that contains a blocked keyword is withheld in enforce mode. An answer that contains personal data is withheld or returned with the data replaced. These checks run before an answer is stored in the cache, so a cached answer is the one the caller saw.

## 7. Audit: what happened?

After the reply is returned, the gateway writes the request, the policy decisions, the routing decision and the final cost to the audit log. This is done in the background, so it never slows the reply. Entries are written once and not edited. You can query the log, filter it by label, and export it for a review. See [Audit logging](/security/audit-logging).

## The same request, three outcomes

| Setup | What the support tool gets |
|---|---|
| Policy in enforce mode, personal data check on | A `446` and a sentence it can show. The model never sees the ticket. |
| Policy in log-only mode | The summary, and a recorded hit you can review. |
| Policy off, cache on | The summary, and the ticket text is stored in the cache as sent. |

The third row is the reason to start with policy on. Caching stores what it is given.

## What to do now

- Give each application its own key, tied to a team, with a daily budget.
- Turn policy on in log-only mode for a week, and read the hits.
- Move to enforce for the checks you trust, such as personal data and the model allow list.
- Decide which data classes may go to which models, then switch routing on.
- Turn on response checks for the apps that talk to customers.
- Look at the log for refusals and spend each week.

## Good to know

Policy checks run on the prompt text, so keep keyword lists specific. The prompt injection check is a heuristic and can flag harmless text, so start in log-only mode.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker and no provider key. The console is at http://localhost:5173. If it helps, star the repo or open an issue with the checkpoint you want to see next.

## Sources

- OpenProxyAI docs: [Request pipeline](/core-concepts/request-pipeline), [Policies and guardrails](/core-concepts/policies-and-guardrails), [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets), [Caching](/core-concepts/caching), [Provider routing](/core-concepts/provider-routing), [Audit logging](/security/audit-logging), [Errors and status codes](/api-reference/errors-and-status-codes).

Statements are based on OpenProxyAI's documented behavior at the post date.
