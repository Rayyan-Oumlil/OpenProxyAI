---
slug: test-a-policy-change-on-real-traffic
image: /img/blog/og/test-a-policy-change-on-real-traffic.png
title: "Test a policy change against real traffic before you enforce it"
tags: [product, security]
description: "Save a new rule in log-only mode, read what it would have blocked on live traffic, probe edge cases with the policy preview, then enforce. Nobody is refused until you have seen the evidence."
---

Every policy change is a bet on traffic you cannot fully see. A new keyword looks sharp in review, then matches a product name used by a whole department. A tighter personal data check fires on test data that nobody remembered. The usual fix is to enforce first and apologize later. OpenProxyAI gives you a better order: record what a rule would do on real requests, look at the evidence, probe the edge cases, and only then turn on refusals.

{/* truncate */}

![Four stages for a policy change: save it in log-only mode, read what real traffic would have triggered, probe edge cases with a preview that sends nothing, then enforce.](/img/blog/test-a-policy-change-on-real-traffic.svg)

## The problem

A guardrail has two kinds of errors. A rule that is too loose lets something through. A rule that is too strict refuses honest work, and the person who pays is a developer with a deadline. Both are cheap to fix if you find them before enforcement, and expensive after, because a refused request is a visible failure and a support ticket.

Only your own traffic finds these errors. So the question is how to put a new rule in front of real requests without letting it act.

## Three tools, three jobs

OpenProxyAI has one policy per organization. Three features let you test a change against it without breaking anyone.

| Tool | What it answers | Does it touch live traffic? |
|---|---|---|
| Log-only mode | What would this rule have done to real requests? | Yes, every request is checked, none is refused |
| Policy activity | How often, and for which reason? | No, it reads the audit log |
| Policy preview | What happens to this one request I am worried about? | No, nothing is sent anywhere |

**Log-only mode.** The enforcement mode has three settings: off, log-only and enforce. In log-only, a rule that fires is recorded in the audit log and the analytics, and the request goes through to the model as normal. The mode applies to the whole policy, not to single rules.

**Policy activity.** Hits are counted by reason and by action over a time range, in the console and through the analytics API. You can also export the individual events, each with a request id, so you can open the real row and see which model, which team and which key were involved.

**Policy preview.** An admin describes a hypothetical request: a model, a message, and optionally a data class. The gateway runs the same classification, policy and routing steps it would run for a real request, then stops. The answer shows the data class it was given, the policy verdict with its reason, which model would serve it and why others were ruled out. No provider is called, no audit row is written and no budget is used. Rate limits and the cache are not part of the preview.

## The plan

### 1. Save the change in log-only

Switch the policy to log-only, then add or edit the rule. Policy changes apply within about a minute. From here on, every request is evaluated against the new rule, and nobody is refused. Tell teams what you are doing.

### 2. Let a full business cycle pass

A rule that looks clean on a Tuesday can misfire on the first of the month. Month-end jobs and weekly reports are the ones that surprise you.

### 3. Read the activity

Open the policy activity and group by reason. Two patterns matter.

- **A rule with many hits on harmless requests.** That is a false positive. Make the keyword more specific, narrow the data types, or drop the rule. For the shape of the work, see [Roll out AI guardrails without breaking teams](/blog/roll-out-guardrails-without-breaking-teams).
- **A rule with no hits at all.** It may be written the way you meant, or it may match nothing. Send a test request that should trigger it and confirm the hit appears.

Export the events for a sample period and open a few real rows. The reason code and the rule that fired are on each one.

### 4. Probe edge cases with the preview

Real traffic tells you what happened. The preview lets you ask about what has not happened yet. Build a short list of requests that worry you:

- A prompt that contains the new keyword inside a harmless sentence.
- A prompt with a number that looks like a card number but is an order id.
- A request for a model that is not on your approved list.
- The sensitive prompt you most want the rule to catch.

Run each one through the preview. While the policy is in log-only, the preview shows the action as log-only together with the reason, so you see exactly which rule would fire. Because it sends nothing, you can run it as often as you like and share the results with the team that owns the prompt.

### 5. Enforce, and check what callers will read

Switch to enforce. A refused request now returns HTTP 446 with a reason code for code and a one-sentence explanation for people. Once the policy is enforcing, the preview also shows the exact sentence a caller would be told, so you can judge the wording before anyone sees it. See [Refusals should explain themselves](/blog/refusals-should-explain-themselves).

Keep reading the activity after you enforce. New teams and new prompts bring new hits.

## A worked scenario

A finance platform team wants to stop client account details from leaving the company in prompts. They add three keywords and turn on personal data detection.

| Day | Mode | What they saw | What they did |
|---|---|---|---|
| 1 | Log-only | The rule is saved. Traffic flows as usual. | Told the teams. |
| 5 | Log-only | One keyword fires on a support team's ticket template. | Replaced it with a longer phrase. |
| 9 | Log-only | Preview of an order-id prompt shows no personal data hit. | Kept the detector on. |
| 14 | Log-only | After month-end, hits are few and all expected. | Read the exported events with the owners. |
| 15 | Enforce | Refusals carry a clear sentence. | Watched the activity for a week. |

Nobody was refused for the wrong reason, and the one keyword that would have caused a week of tickets was fixed on day 5.

## What to do now

1. Switch the policy to log-only before you add the new rule.
2. Announce the test window and the enforcement date.
3. Wait a full business cycle, then read the activity grouped by reason.
4. Export a sample of events and open a few rows.
5. Write five edge-case requests and run them through the preview.
6. Enforce, then check the refusal sentence in the preview and in your application.

## Good to know

The mode is one switch for the whole policy, so finish testing every rule before you flip it. The preview uses the policy as saved, so save your change first (the console tells you when you have unsaved edits). Keyword checks are plain, case-insensitive matches on the request text, which is why short or common words cause most false positives.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. The demo policy already blocks one keyword and personal data; switch it to log-only on the Policy page, send the blocked example prompts again, and watch them pass and appear as log-only hits in the request logs. If it helps, star the repo or open an issue.

## Sources

- OpenProxyAI docs: [Policies and guardrails](/core-concepts/policies-and-guardrails), [Managing your organization](/admin-console/managing-your-organization), [Analytics](/api-reference/analytics), [Errors and status codes](/api-reference/errors-and-status-codes), [Compliance templates](/security/compliance-templates), [Audit logging](/security/audit-logging).
- On this blog: [Roll out AI guardrails without breaking teams](/blog/roll-out-guardrails-without-breaking-teams), [Refusals should explain themselves](/blog/refusals-should-explain-themselves), [An audit trail your auditor can read](/blog/an-audit-trail-your-auditor-can-read).

These statements are based on OpenProxyAI's behavior and docs as of October 21, 2026.
