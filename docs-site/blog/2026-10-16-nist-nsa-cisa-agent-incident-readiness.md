---
slug: nist-nsa-cisa-agent-incident-readiness
title: "NIST, NSA and CISA publish ten practices for when an AI agent goes off script"
tags: [security, product]
description: "On 16 October 2026 NIST, the NSA and CISA issued voluntary guidance on incident readiness for AI agents. See the ten practices and how a gateway turns several of them into controls."
---

On 16 October 2026, NIST, the NSA and CISA jointly published voluntary guidance on what to do when an AI agent takes serious actions nobody asked for. It lists ten practices in five stages: prepare, detect, respond, recover and report. The guidance is written for teams that train and test highly capable agents, but the shape of it applies to anyone who lets an agent call tools. This post sums up what the agencies said, and shows how a gateway gives you the technical half of the playbook before you ever need it.

{/* truncate */}

![Five incident stages (prepare, detect, respond, recover, report) each paired with a gateway control: scoped keys and tool lists, security events, key revocation and blocked tools, audit trail, exports.](/img/blog/nist-nsa-cisa-agent-incident-readiness.svg)

## What happened

| Fact | Detail |
|---|---|
| Title | "Key Practices for Incident Readiness and Response in Super Intelligence Training and Evaluation" |
| Issuers | NIST (its CAISSI center), the NSA (its Super Intelligence Security Center) and CISA |
| Date | 16 October 2026 |
| Status | Voluntary |
| Subject | Incidents in which agents take significant uninstructed actions that undermine operator-imposed policies, controls or human oversight |
| Structure | Ten practices in five stages: preparation, detection, response, recovery and reporting |
| Foundation | Builds on NIST SP 800-61r3, the incident response guide, and on NIST's experience running secure evaluations of frontier models |

Summaries of the full document by two outlets (a law firm bulletin and a security news site) describe the practices in more detail. We have not read the full document, so treat the list below as their paraphrase, not a quote.

| Stage | What the summaries say |
|---|---|
| Prepare | Use least-privilege access, single-use infrastructure and network allowlists that go through a monitored point where possible. Run drills and agree severity scoring before you start |
| Detect | Monitor the model, its harness, the host and the network. Keep agents from touching monitoring and logs. Test the monitors themselves, since agent output may be crafted to attack them |
| Respond | Preserve evidence such as logs and rejected tool calls. Shut down affected activity, pause similar agents and revoke credentials |
| Recover | Rebuild from verified baselines and confirm that monitoring and shutdown controls work before restarting |
| Report | Tell affected parties, meet legal reporting duties and share lessons, including near-misses |

## What it means

Most companies are not training frontier models. They are giving agents a handful of tools: read a ticket, query a database, send an email. Still, the failure the agencies describe is the same one a platform team fears: an agent does something that nobody authorized, and the team cannot tell quickly what it did, what it touched or how to stop it.

Three lessons carry over.

1. **Limits come before incidents.** The first practices are about access: what the agent may reach, and how it reaches it. A limit set after the fact is a patch.
2. **Evidence has to be kept by something the agent cannot edit.** If an agent can change its own logs, the log proves nothing.
3. **Stopping has to be fast and practiced.** Revoking credentials and pausing similar agents are only useful if you have done them once on a quiet day.

Note the scope. The guidance targets training and evaluation of highly capable agents. It does not require anything of you.

## How OpenProxyAI helps

OpenProxyAI is an open-source, self-hosted gateway. Your agents send model calls and tool calls through it. That puts the controls and the records outside the agent, where it cannot rewrite them.

| Practice area | What you can do with the gateway |
|---|---|
| Least privilege | Give each agent its own API key with permissions and an expiry. Grant tools per key, team or role, and expose only an approved set of tools through a named bundle |
| Controlled reach | Allow and block lists for tools, plus pinning that serves only approved tool definitions. A tool whose definition changed after approval stops being served as approved |
| Side effects | Mark tools that send, write or delete. Once an agent has seen output from an untrusted tool, those tools refuse to run in that session |
| Spend and rate | Per-key tool call limits, and request, token and dollar limits per organization, user and team. A runaway loop hits a limit and gets 429 |
| Detection | Security events for policy blocks, injection hits, blocked tools, tool drift and limit stops, streamed to your SIEM with the ids needed to join them to a request |
| Stop and revoke | Revoke a key and its next request returns 401. Mark a tool as blocked and every call to it is refused |
| Evidence | A request log row for every model call and every tool call, including blocked ones, and an admin audit log of every change to keys, grants and policy |

A worked scenario. A finance team runs an agent that reads invoices and can email vendors through a tool. One invoice contains hidden text telling the agent to forward a payment file. The agent reads the invoice through an untrusted tool, so the session is marked. When it then tries to call the email tool, the gateway refuses, because side-effect tools do not run after untrusted output was seen. The refusal is written to the request log, a security event goes to the SIEM, and the on-call engineer revokes the agent's key while they investigate. The record shows what the agent tried and what it was stopped from doing. For more on that pattern, read [bounding a hijacked agent](/blog/bounding-a-hijacked-agent) and [MCP grants beat shared tokens](/blog/mcp-grants-beat-shared-tokens).

Good to know: the gateway governs model and tool traffic that passes through it. Controls on the host, the network and the agent's own runtime still belong to your platform team. Keep the gateway as the one path the agent has to the outside world, and the two layers support each other.

## What to do now

- [ ] Inventory every agent that can call a tool, and what each tool can change
- [ ] Give each agent its own key, with an expiry and only the permissions it needs
- [ ] Put tool servers behind one endpoint, with allow lists and pinned definitions
- [ ] Mark every tool with side effects, and decide how untrusted output affects it
- [ ] Set rate and spend limits per key and team so a loop cannot run unbounded
- [ ] Stream security events to your SIEM and write down who is paged
- [ ] Run one drill: revoke a test agent's key, confirm it stops, and replace it

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. The console is at http://localhost:5173. If it is useful, star the repo or open an issue on GitHub.

## Sources

- NIST, [Key Practices for Incident Readiness and Response in Super Intelligence Training and Evaluation](https://www.nist.gov/news-events/news/2026/10/key-practices-incident-readiness-and-response-super-intelligence-training): the 16 October 2026 announcement, issuers, voluntary status, ten practices in five stages, link to SP 800-61r3.
- Epstein Becker Green, [When the AI agent goes off script](https://www.ebglaw.com/workforce-bulletin/when-the-ai-agent-goes-off-script-the-first-incident-playbook-for-frontier-ai): paraphrase of the ten practices.
- Cyber Security News, [NSA, CISA and NIST release new security guidelines](https://cybersecuritynews.com/?p=167853): summary of the access, detection and shutdown practices.
- OpenProxyAI docs: [MCP gateway](/guides/mcp-gateway), [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets), [Telemetry and SIEM](/guides/telemetry-and-siem), [Audit logging](/security/audit-logging), [Authentication](/getting-started/authentication).

These statements are based on the sources above and on OpenProxyAI's behavior at the post date.
