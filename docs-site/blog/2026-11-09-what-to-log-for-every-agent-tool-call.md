---
slug: what-to-log-for-every-agent-tool-call
title: "What to log for every agent tool call, and where OpenProxyAI records it"
tags: [security, engineering]
description: "A tool call by an agent should leave a record that answers who, under what permission, with which tool version, what the policy decided and what it cost. Here is the minimum, mapped to OpenProxyAI."
---

When an agent sends an email, opens a ticket or deletes a file, someone will eventually ask what happened and why it was allowed. If the answer is "we think the agent did it", you have a logging gap. A good tool call record is small and specific. It answers five questions, and you can write them down before you build anything. This post lists them, explains why each one earns its place, and shows what OpenProxyAI records for each tool call that passes through its MCP gateway.

{/* truncate */}

![An agent tool call passes through the gateway, which writes one audit row with five answers: the requester, the grant that applied, the tool version status, the policy decision and the cost.](/img/blog/what-to-log-for-every-agent-tool-call.svg)

## The minimum record

| Question | Why you need it |
|---|---|
| **Requester.** Which person, application key and team made the call? | Accountability. An agent is not a person, so the record must point to the human or the service that owns it. |
| **Grant.** What permission allowed it? | Lets you check later that the permission was intended, and spot a grant that is too wide. |
| **Tool version.** Which definition of the tool did the agent see? | Tool descriptions change. If a call went wrong, you need to know whether the description had changed since approval. |
| **Policy decision.** Allowed, flagged or blocked, and the rule that fired? | Proves that your controls ran, and shows which ones are noisy. |
| **Cost and size.** What did this cost, how long did it take? | Lets finance and operations attribute spend and find slow tools. |

Add three supporting fields that are cheap and save hours: a timestamp, an outcome (success, upstream error or refusal), and a stable identifier you can search for.

What not to log by default: the full arguments and results. They often hold personal or confidential data. Record the decision and the identifiers first. Keep payloads only where you need them and only after redaction.

## What OpenProxyAI records

Every tool call through the MCP gateway writes one row to the request log. The row sits next to model calls, so one query and one export cover both. Here is how the five answers map.

| Question | In the record |
|---|---|
| Requester | The user, the API key and, where the key belongs to a team, the team. The log can be filtered by team, and the detail view shows the user and key. |
| Grant | The access that applied, meaning which grants and which request scope shaped what the caller could reach. |
| Tool version | The pin status of the tool at call time (approved, pending, drifted or blocked, or unpinned). The approved definition and its previous version are visible in the tool review screen and the admin API. |
| Policy decision | The decision and the rules that fired. A call refused by policy is recorded with status 446, the same code as a model call blocked by a guardrail. Upstream failures show as 502. |
| Cost and size | Latency for every call. Model calls carry tokens and cost. |

The row also holds the tool name and the server it ran on, whether the session had been tainted by untrusted output, and any findings from description or result scanning. Findings are category names, not copied text.

The record is metadata only. Prompts, tool arguments and results are not stored unless an admin turns on payload capture, which stores a redacted sample. See [Payload capture](/guides/payload-capture).

## Changes are logged too

Tool calls are only half the story. The other half is who changed the rules. The admin audit log records each change to servers, tool approvals, grants, bundles and trust rules, with the actor, the time, and the before and after values. It is written in the same transaction as the change, so a change cannot succeed without its record.

When someone asks "why could the agent call that tool", you can answer in two lookups: the call row shows which grant applied, and the admin log shows who created that grant and when.

## Tying tool calls to spend

Tool calls themselves are not priced by the gateway, so cost shows up on the model calls around them. To see the full cost of an agent task, tag the work. Requests can carry labels and a session id, and the request log can be filtered by both, so an agent run becomes one slice you can total. This is the same approach described in [know who spends what on AI](/blog/know-who-spends-what-on-ai).

## Searching and exporting

- **Console and API.** List and filter the request log by date, status, policy action, team, label and session. Open one entry for the full detail.
- **Compliance export.** An admin can export a period of policy violations, access, provider key rotations and budget against actual spend as a spreadsheet.
- **Policy export.** Policy events, with request identifiers, as JSON or CSV.
- **Streaming.** Send events to your SIEM as they happen. They carry identifiers and reason codes, not prompt text.

Rows are append-only from the gateway's point of view: the database role it uses cannot delete log rows. Retention follows the plan, from days to a year, and archived rows can still be listed. If your framework needs longer history, export on a schedule. See [an audit trail your auditor can read](/blog/an-audit-trail-your-auditor-can-read).

## A worked example

An agent called a delete tool on a ticketing server and an engineer wants to know why it was allowed.

1. Filter the request log by that tool name and date. The row shows the user, the key and the team.
2. Read the access data on the row. It shows the grant that matched the key's role.
3. Read the pin status. It says approved, so the definition had not drifted.
4. Read the decision. It was allowed, with no rule fired.
5. Open the admin log for that grant. It was added three weeks earlier by a named admin.

The finding is clear: the permission was granted on purpose, and the fix is to narrow the grant, not to chase a mystery.

## What to do now

1. Write down your five questions for each class of tool, especially those with side effects.
2. Put all tool servers behind the gateway so every call writes the same record.
3. Give each agent its own key and team, so the requester is never "shared".
4. Label agent runs so spend can be totaled.
5. Turn on SIEM streaming and schedule the compliance export.
6. Review the admin audit log monthly for grants, approvals and trust rule changes.

## Good to know

Tool calls are recorded with zero tokens and zero cost, because pricing belongs to model calls. Use labels and session ids to connect the two.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. Star the repo or open an issue if there is an audit question you cannot answer yet.

## Sources

- OpenProxyAI docs: [Audit logging](/security/audit-logging), [MCP gateway](/guides/mcp-gateway), [MCP admin API](/api-reference/mcp-admin), [Telemetry and SIEM](/guides/telemetry-and-siem), [Payload capture](/guides/payload-capture).
- On this blog: [An audit trail your auditor can read](/blog/an-audit-trail-your-auditor-can-read), [MCP grants beat shared tokens](/blog/mcp-grants-beat-shared-tokens), [Know who spends what on AI](/blog/know-who-spends-what-on-ai).

These statements are based on OpenProxyAI's behavior at the post date.
