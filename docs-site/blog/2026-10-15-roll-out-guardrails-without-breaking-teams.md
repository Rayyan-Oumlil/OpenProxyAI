---
slug: roll-out-guardrails-without-breaking-teams
image: /img/blog/og/roll-out-guardrails-without-breaking-teams.png
title: "Roll out AI guardrails without breaking teams: log first, then enforce"
tags: [product, security]
description: "Turn on guardrails in log-only mode, read the policy activity to find noisy rules, then enforce with plain-language refusals. A rollout plan that keeps developers on your side."
---

The fastest way to lose a developer's trust is to block their requests on day one with a rule they have never heard of. The fastest way to lose your security team's trust is to have no rules at all. OpenProxyAI gives you a middle path: run every rule in log-only mode, read what it would have blocked, fix the noise, then enforce. Here is the plan, step by step.

{/* truncate */}

![Three steps: log-only records hits while requests still pass, read the activity to tighten noisy rules, then enforce so blocked requests get a 446 and a plain reason.](/img/blog/roll-out-guardrails-without-breaking-teams.svg)

## The problem

Guardrails are guesses until they meet real traffic. A keyword list that looks sharp in a meeting matches a harmless internal project name. A personal data check fires on a test fixture. If those rules block from the start, teams file tickets, then route around you. If you never turn them on, the rules protect nothing.

You need evidence before you block. That is what log-only mode is for.

## The three modes

The organization policy has one enforcement mode:

| Mode | What a rule that fires does |
|---|---|
| Off | Nothing is checked. |
| Log-only | The hit is recorded in the audit log and analytics. The request goes through. |
| Enforce | The request is refused with HTTP 446 and a one-sentence explanation. |

The checks you can set up include a model allowlist, blocked keywords, personal data detection (emails, US Social Security numbers, payment card numbers, with more types available through an optional detector), and prompt-injection detection. You can also check responses, and add your own rules as policy plugins.

## The plan

### Step 1: Start in log-only

Pick a small set of rules, switch the policy to log-only, and tell teams what you are doing. Nothing changes for them. Behind the scenes, every hit is written down with its reason code.

Want to try a rule on a sample before it touches live traffic? The console has a policy preview. Describe a hypothetical request and it shows whether the policy would block it, which model would serve it and why other models were ruled out, without sending anything upstream or using any budget.

### Step 2: Read the policy activity

The console's policy activity table shows hit counts over a time range, and the same data is available through the analytics API and as an export. You are looking for two things:

- **A rule that fires a lot on legitimate traffic.** That is a false positive. Make the keyword more specific, narrow the list, or drop the rule.
- **A rule that never fires.** Check that it is configured the way you meant.

Spend a full business cycle here, so month-end jobs and weekly reports show up in the data.

### Step 3: Talk to the teams that hit rules

Hits are tied to teams and keys, so you know who to ask. A short message works: "This rule would have blocked your nightly job. Is that expected?" You will often learn something the rule needed to know.

### Step 4: Enforce

Switch to enforce mode. Blocked requests now get a 446 with a plain-language explanation the application can show to a user, plus a reason code for code to act on. A refused request is not retryable as it stands: the content has to change or the policy does. Tell teams to show the explanation and not a generic error.

### Step 5: Keep watching

After enforcing, the activity table keeps working. New teams and new prompts bring new hits. Review it on a schedule and adjust.

## A worked scenario

A finance team adds three rules: a model allowlist, personal data detection and a keyword list of project code names.

| Week | Mode | What the activity showed | Action |
|---|---|---|---|
| 1 | Log-only | The keyword list matched a harmless internal tool name used by a support team. | Remove that term, make the others more specific. |
| 2 | Log-only | Personal data detection fired on a test suite that sends fake card numbers. | Move the tests to a test organization. |
| 3 | Log-only | Allowlist hits show one team using a model nobody approved. | Review it, then approve it or move the team. |
| 4 | Enforce | Few hits, all expected. | Teams see clear refusals and fix prompts. |

## What to do now

1. Pick a first set of rules and set the policy to log-only.
2. Announce the rollout and what will change on the enforcement date.
3. Read the policy activity at least weekly. Fix false positives first.
4. Contact the teams behind the remaining hits.
5. Switch to enforce. Make sure applications show the refusal explanation.
6. Schedule a monthly review of the activity table.

## Good to know

The enforcement mode applies to the whole policy, not to each rule on its own. Before you flip it, make sure every rule has had its review in log-only mode. Policy checks run on the request text, so keep keyword lists specific. In enforce mode, personal data in a request blocks it, and the gateway does not rewrite the request. If you want requests with personal data to stop, that is the setting. Compliance templates replace the guardrail settings in one call, so review the keyword list after applying one. See [Managing policies](/admin-console/managing-your-organization).

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If it helps, star the repo or open an issue.

## Sources

- OpenProxyAI docs: [Policies and guardrails](/core-concepts/policies-and-guardrails), [Managing policies](/admin-console/managing-your-organization), [Errors and status codes](/api-reference/errors-and-status-codes), [Compliance templates](/security/compliance-templates), [Audit logging](/security/audit-logging).
- On this blog: [Keys will leak: design so a leaked application key is a nuisance](/blog/a-leaked-key-should-be-a-nuisance).

These statements are based on OpenProxyAI's behavior and docs as of October 15, 2026.
