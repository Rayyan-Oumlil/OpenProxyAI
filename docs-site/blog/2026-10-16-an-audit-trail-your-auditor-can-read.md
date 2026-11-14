---
slug: an-audit-trail-your-auditor-can-read
title: "An AI audit trail your auditor can actually read"
tags: [security, product]
description: "What OpenProxyAI records for every model and tool call, how admins search and export it, how long each plan keeps it, and how to answer an auditor's question in minutes instead of days."
---

Sooner or later someone asks a plain question about your AI systems. Who used the model that handled this customer's data? Why was this request refused? What did the assistant cost in March? If the honest answer is "let me check a dozen log files", the audit is going to be slow. A good audit trail is not a pile of logs. It is one record per call, in one place, with the same fields every time, that a person who is not an engineer can read.

{/* truncate */}

![A request flows through the gateway and becomes one audit row with who, what, decision and cost. Admins filter the log in the console, open a request trace, and export a report. Retention depends on the plan.](/img/blog/an-audit-trail-your-auditor-can-read.svg)

## What is recorded for each request

Every request that passes through OpenProxyAI becomes one record, written after the response has gone back to your application, so a slow log never slows a user down. Tool calls from agents that use the MCP gateway get the same treatment.

| Question | What the record holds |
|---|---|
| Who? | The organization, the user and the API key that made the call, and the team or labels you attached |
| What? | The model and provider, and for a tool call, the tool name |
| How much? | Prompt, answer and total tokens, and the cost |
| How fast? | Latency, and time to first token for streamed answers |
| What happened? | The status, and an error message when there was one |
| What did policy decide? | Allowed, flagged or blocked, with the reason |
| Where did it go? | The routing decision, and whether a cache answered |
| What kind of data? | The data class assigned to the request, and the kinds of personal data found, never the data itself |

Entries are write-once. Nothing in the request path edits an entry after it is written, so the record shows what happened, not a status that drifted later.

The text of prompts and answers is not stored in the audit record by default. That keeps the log useful for investigation without turning it into a second copy of your sensitive data. Teams that want real examples to evaluate changes can opt in to a redacted sample, which is off until you set a rate. See [Capturing traffic for evaluation](/guides/payload-capture).

Admin actions are recorded too. Creating a key, changing a policy, registering a tool server: each lands in a separate admin audit log with a before and after view of what changed. That answers "who changed the rule, and when".

## Searching it

In the admin console, the request log is a filterable table. Admins can narrow it by:

- model
- success or error
- policy outcome (allowed, log-only or blocked) and the policy reason
- label, for example one application
- team
- session
- date range

Open any row to see its details, and open the request trace to see where the time went across authentication, policy, rate limiting, the cache and the provider. The same filters are available through the API, so a script or a notebook can ask the same questions. See [Analytics](/api-reference/analytics).

A typical audit question and where the answer lives:

| Question | How to find it |
|---|---|
| Which requests were refused last month, and why? | Filter by policy outcome blocked and a date range |
| What did the finance app spend? | Filter by its label or team |
| Did anyone call this tool? | Filter the tool calls by tool name and read the decisions |
| Who changed the policy on the 3rd? | Open the admin audit log and read the diff |

## Exporting it

Admins can export a compliance report as a CSV file, for a period of up to a year. It brings together policy violations, user access, key rotations and budget against actual spend, in a format you can hand to an internal or external reviewer. A policy event export is available as JSON or CSV, filtered by date, outcome and reason. Spreadsheet cells in the exports are sanitized so a hostile value cannot run as a formula when someone opens the file.

If you run a security monitoring system, an optional export can stream security events, such as policy blocks, budget stops and tool refusals, to your SIEM in a standard format. Those events carry identifiers and reason codes, never prompts or tool arguments. See [Telemetry and SIEM export](/guides/telemetry-and-siem).

## How long it is kept

Retention follows the organization's plan.

| Plan | Audit log retention |
|---|---|
| Community | 7 days |
| Team | 30 days |
| Business | 90 days |
| Enterprise | 365 days |

Older entries are archived on a regular background schedule once they pass the window. The compliance templates record a longer retention target in the policy as a reminder of what a framework may expect, but the window that actually applies is the one set by the plan. If your framework needs a longer period than your plan, export on a schedule and keep the files where your records policy says. See [Audit logging](/security/audit-logging).

## Make it part of the routine

An audit trail helps most when someone looks at it before the auditor does.

- [ ] Route every model call and every agent tool through the gateway, so nothing happens off the record.
- [ ] Attach a team and a label to each application so cost and activity can be split.
- [ ] Run new policies in log-only mode first and read what they would have blocked.
- [ ] Review blocked requests and admin changes on a set schedule.
- [ ] Compare your plan's retention with what your framework expects, and schedule exports if you need more.
- [ ] Do a dry run: pick a past request and see how fast you can explain it.

## Good to know

The gateway records the traffic that goes through it, so the trail is only as complete as your routing. Keep applications on gateway keys and remove direct provider keys. The trail supports your audit, and your own program and reviewer decide what satisfies a given framework. OpenProxyAI provides controls and templates, not a certification.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

This needs Docker and no provider key. The console opens at http://localhost:5173 with sample traffic, including blocked requests, so you can try the filters straight away. If it helps, star the repo or open an issue with the report you wish you had.

## Sources

- Internal: [Audit logging](/security/audit-logging), [Analytics](/api-reference/analytics), [Telemetry and SIEM export](/guides/telemetry-and-siem), [Capturing traffic for evaluation](/guides/payload-capture), [Compliance templates](/security/compliance-templates), [Request pipeline](/core-concepts/request-pipeline).

These statements are based on OpenProxyAI's behavior at the date of this post.
