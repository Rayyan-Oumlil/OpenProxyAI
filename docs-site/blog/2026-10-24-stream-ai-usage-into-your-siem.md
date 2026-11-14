---
slug: stream-ai-usage-into-your-siem
image: /img/blog/og/stream-ai-usage-into-your-siem.png
title: "Stream AI usage into your SIEM and observability stack, without touching the request path"
tags: [security, engineering]
description: "Send one OpenTelemetry span per model call and a security event for every block, budget stop or rate limit to your SIEM. No prompts leave the gateway, and a slow collector never slows a request."
---

Your security team already watches firewalls, identity and cloud logs in one place. AI traffic is usually missing from that picture. When a policy blocks a prompt, a key hits its budget or a tool call is refused, the people who triage alerts often do not see it. OpenProxyAI can send two streams to the tools you already run: one trace span per model call for your observability stack, and a security event for every block for your SIEM. Both are optional, and both are designed so that exporting can never make a request slower or fail.

{/* truncate */}

![The gateway sends one trace span per request to an OpenTelemetry collector and security events to a SIEM. Prompts and completions are never included.](/img/blog/stream-ai-usage-into-your-siem.svg)

## Two streams, two audiences

| Stream | For | What you get |
|---|---|---|
| OpenTelemetry traces | Platform and SRE teams, cost and latency views | One span per finished request: chat, embeddings, rerank, images, audio and Responses, plus one per MCP tool call |
| SIEM events | Security operations | One event for each policy block, budget stop, rate limit and MCP refusal, in CEF or JSON |

Both are off until you turn them on in your deployment settings. If you do nothing, nothing is sent.

## What a trace span tells you

Each span follows the OpenTelemetry conventions for generative AI, so tools that understand those conventions can chart it without custom work. A span carries:

- The operation, such as chat or embeddings, and for an MCP call, a tool execution.
- The provider and the model.
- Input and output token counts.
- The status the caller got, with an error status marking the span as an error.
- The request id, the organization id and the cost, so a span can be joined to the request log and to spend.
- The policy action, when policy acted on the request.

It is a spend and latency view that your existing dashboards can show next to your other services, with no new agent to install.

## What a SIEM event tells you

Events are named for what happened, so rules and alerts are easy to write.

| Event | When it fires |
|---|---|
| `AI-POLICY-BLOCK` | A request was refused by policy or by routing |
| `AI-DLP-BLOCK` | A request was refused because of personal or sensitive data |
| `AI-INJECTION-BLOCK`, `AI-INJECTION-FLAGGED` | Prompt injection was detected, blocked or only flagged |
| `AI-BUDGET-EXCEEDED`, `AI-RATE-LIMIT` | A budget or rate limit stopped the request |
| `AI-UNAUTHORIZED-MCP`, `AI-MCP-TOOL-BLOCK`, `AI-TOOL-DRIFT` | An MCP request was refused, or a tool changed after it was approved |
| `AI-TAINT-BLOCK` | A tool-using conversation that had handled untrusted tool output was stopped from using a sensitive tool |

Every event carries the organization, user, key and request identifiers and the model or tool involved. You choose the format (CEF is the default, JSON is available) and where it goes: standard output, a file, or syslog over UDP or TCP. Standard output is handy for a container platform that already collects logs, and syslog suits a traditional SIEM forwarder.

## Never the content

Neither stream includes prompts, completions or tool arguments. A SIEM is widely readable, retained for a long time and often shared with outside parties. Keeping content out means exporting does not create a new place where sensitive text lives. The events tell your analysts that something happened and who it involved, and the audit trail inside the gateway holds the rest. Read more in [an audit trail your auditor can read](/blog/an-audit-trail-your-auditor-can-read).

## Safe for the request path

Observability should never become the reason an application is down. Both exports follow the same rules.

| Rule | What it means |
|---|---|
| Never waits | Sending is handed off in the background. A request does not know whether the export worked. |
| Never fails a request | A slow or broken collector affects only the export, never the caller. |
| Bounded | If a collector is down for a while, new items are dropped and counted, not stored without limit. |
| Quiet failures | Errors are summarized rather than flooding logs, and never print endpoints or credentials. |
| Misconfiguration is loud | A missing endpoint or an unknown format stops the gateway at startup. It does not silently turn export off. |

The last row follows a principle worth copying elsewhere: if you asked for security events to be exported and the setup is wrong, you want to find out immediately, not after an incident.

## A worked scenario

A security operations team wants AI activity in the same console as everything else.

1. Platform sets up the syslog sink toward the existing forwarder, in CEF format, and the tracing endpoint toward the existing collector.
2. In the SIEM, an analyst writes three rules: any prompt injection block, more than a few DLP blocks from one user in an hour, and any tool whose definition changed after approval.
3. On Tuesday, the DLP rule fires. The event names the user, the key and the model, but not the prompt text. The analyst opens the gateway's audit log for that request id to see the reason, and calls the user's manager.
4. In the observability stack, the platform team charts tokens and cost per model next to their service latency, and spots one team sending a lot of embeddings calls to an expensive model.

The SIEM and the dashboards needed no custom integration, only a standard format.

## What to do now

- [ ] Decide who consumes each stream: security operations for events, platform for traces.
- [ ] Turn on events first if you can only do one. They give the highest security value.
- [ ] Pick the format your SIEM parses best, and the sink your infrastructure already supports.
- [ ] Write three alert rules before you go live: injection blocks, repeated DLP blocks, tool changes.
- [ ] Join spans to the request log with the request id when you investigate.

## Good to know

Events record that something was refused and why, by design not the text that triggered it. When an analyst needs more, they follow the request id back to the gateway's own audit log, which has its own access controls and retention.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

This needs Docker and no provider key. The console is at http://localhost:5173. If it helps you, star the repo, and if your SIEM needs a format we do not offer, open an issue.

## Sources

- [Telemetry and SIEM export](/guides/telemetry-and-siem): the spans, the events, the formats, the sinks and the safety rules.
- [Audit logging](/security/audit-logging): the full record behind each event.
- [Webhooks](/guides/webhooks): signed alerts for policy and budget events.
- [Protect every prompt end to end](/blog/protect-every-prompt-end-to-end): the checks that produce these events.
- [Budgets that fail closed](/blog/budgets-that-fail-closed): the limits behind the budget events.

These statements are based on the sources above and on OpenProxyAI's behavior as of 2026-10-24.
