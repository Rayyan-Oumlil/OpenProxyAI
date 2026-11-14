---
slug: en-18286-first-ai-act-standard
image: /img/blog/og/en-18286-first-ai-act-standard.png
title: "EN 18286 is the first AI Act standard. Here is the evidence it will ask for"
tags: [security, product]
description: "On 14 October 2026 the EU cited its first harmonised standard for the AI Act, a quality management standard. See what it covers and which evidence a gateway can produce for it."
---

On 14 October 2026 the European Commission cited the first harmonised standard under the EU AI Act in the Official Journal. It is EN 18286:2026, a quality management standard for AI providers. Providers of high-risk AI systems now have a published yardstick that carries a legal presumption for part of the Act. If your teams build on top of models, you will soon be asked what evidence you keep. This post explains what happened, what it means, and how a gateway helps you collect that evidence.

{/* truncate */}

![A flow from the standard's topics (requirements, post-market monitoring, supply chain, incident reporting) to evidence the gateway produces: audit log, usage analytics, model and provider inventory, policy hit exports.](/img/blog/en-18286-first-ai-act-standard.svg)

## What happened

| Fact | Detail |
|---|---|
| Standard | EN 18286:2026, "Artificial intelligence, Quality management system for EU AI Act regulatory purposes", prepared by CEN and CENELEC |
| Legal act | Commission Implementing Decision (EU) 2026/2274 |
| Date | Cited in the Official Journal on 14 October 2026 |
| Effect | Under Article 40 of the AI Act, a provider that applies a harmonised standard whose reference is published in the Official Journal is presumed to conform with the requirements that standard covers |
| Status | Voluntary. The Commission says the application of standards remains voluntary, and providers may use other frameworks to show compliance |

A law firm summary of the standard describes what it asks providers to do. They identify the AI Act requirements that apply to them, define the scope of their quality system, and keep a documented compliance strategy. The standard also covers the essential requirements for high-risk systems (Articles 9 to 15), conformity assessment, changes to a system, post-market monitoring, serious-incident reporting, lifecycle processes, supply chain controls and management review. The same summary warns that a general quality standard such as ISO/IEC 42001 does not on its own give the presumption, and that the presumption covers only what EN 18286 covers.

## What it means

Three practical points for platform and security leads.

1. **The Act now has a concrete yardstick.** Before this citation, "quality management system" was a phrase in the Act. Now there is a named standard that an auditor or a customer can point to.
2. **It reaches the supply chain.** The standard covers supply chain controls. If your product calls external models, you need to know which models and providers you use, and for which data.
3. **It is about evidence.** A quality system lives on records: what ran, who changed what, what was blocked, what went wrong, and what you did next. Those records have to come from somewhere other than memory.

Keep one expectation straight. Citing a standard does not make anyone compliant. Your legal duties, your risk assessment and your own audit remain yours. A gateway cannot supply a quality management system, but it can supply a large share of the technical records one relies on.

## How OpenProxyAI helps

OpenProxyAI is an open-source, self-hosted gateway that sits between your applications and every model provider. Because all model traffic crosses one point, the records you need are produced as a side effect of normal use.

| What a quality system needs | What the gateway gives you |
|---|---|
| A record of what ran | A request log with one entry per request: model, provider, tokens, cost, status, and the policy decision. Prompt text is not stored unless an admin switches payload capture on |
| A record of who changed what | An admin audit log of policy, key, model and tool changes, written in the same step as the change itself |
| An inventory of models and providers | A model registry and routing rules that state which model may see which class of data |
| Post-market monitoring | Usage analytics, error rates, cost and user feedback tied to each request |
| Incident evidence | Exports of every blocked or flagged request with its reason code, plus security events streamed to your SIEM |
| Change control | Quality checks that replay saved examples against a candidate model or policy before you ship it |

A simple scenario shows how this fits together. A provider team preparing a high-risk system lists the external models it depends on. They put all calls behind the gateway, restrict the allowed models to that list, and set routing so sensitive data classes reach only approved providers. Months later, an assessor asks which model version served requests in a given week, who approved a policy change, and how many requests were refused. The team exports the request log and the policy events for that period and points to the admin audit entry for the change. The answer takes minutes, not a search through application logs.

The [compliance templates](/security/compliance-templates) in the product are starting configurations for guardrails, not certifications. They do not make a deployment conform to EN 18286 or to any other framework. We wrote about this line in [compliance templates, not badges](/blog/compliance-templates-not-badges).

Good to know: the request log keeps metadata for a period that depends on your plan. If your quality system needs a longer history, export on a schedule or stream the events to your own store.

## What to do now

- [ ] Read the Commission's page on AI Act standardisation and decide whether EN 18286 is your route to the presumption or whether you will use another framework
- [ ] List every external model and provider your AI features call, and the data each one may see
- [ ] Route all model traffic through one gateway so every call leaves a record
- [ ] Restrict allowed models to your approved list and set data-class routing for sensitive prompts
- [ ] Decide how long you must keep request and change records, and schedule exports for anything longer than your plan retains
- [ ] Test a policy or model change on saved examples before you roll it out, and keep the result
- [ ] Ask your legal team which AI Act duties apply to you as a provider, and which to you as a deployer. Our [engineer's guide to the EU AI Act](/blog/eu-ai-act-for-engineers) is a place to start

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. The console is at http://localhost:5173. If it is useful, star the repo or open an issue on GitHub.

## Sources

- European Commission, [AI Act standardisation](https://digital-strategy.ec.europa.eu/en/policies/ai-act-standardisation): describes EN 18286, the Official Journal reference 2026/2274, the presumption of conformity and the voluntary nature of standards.
- EUR-Lex, [Commission Implementing Decision (EU) 2026/2274](https://eur-lex.europa.eu/eli/dec_impl/2026/2274/oj): the legal act that cites the standard.
- Orrick, [First Harmonised Technical Standard Published Under the EU AI Act](https://www.orrick.com/en/Insights/2026/10/First-Harmonised-Technical-Standard-Published-Under-the-EU-AI-Act): the 14 October 2026 date, the scope of the standard and the limits of the presumption.
- OpenProxyAI docs: [Audit logging](/security/audit-logging), [Compliance templates](/security/compliance-templates), [Data residency](/security/data-residency), [Evaluating changes](/admin-console/evaluating-changes).

These statements are based on the sources above and on OpenProxyAI's behavior at the post date.
