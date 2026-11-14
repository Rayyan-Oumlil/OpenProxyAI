---
slug: quebec-law-25-ai-providers
title: "Quebec's Law 25 and AI providers: what to settle before personal data leaves"
tags: [security, product]
description: "Since 22 September 2023, key Law 25 rules apply, including a privacy impact assessment before personal information leaves Quebec. A neutral guide for teams that send prompts to AI providers."
---

On 22 September 2023, a major set of Law 25 provisions took effect in Quebec. The Commission d'accès à l'information, the province's privacy regulator, announced it the same day. One rule matters a lot to teams that use AI models: before personal information is communicated outside Quebec, the organization must carry out a privacy impact assessment. Many AI providers process prompts outside Quebec. This post explains the rule in plain words, then shows how a gateway helps you know what is being sent and where. It is general information, not legal advice.

{/* truncate */}

![A prompt that may hold personal information gets a data class, then the model registry checks class and region. The request goes to an approved provider or is refused with a clear reason.](/img/blog/quebec-law-25-ai-providers.svg)

## What the regulator says

Law 25 is the common name for the act that modernized Quebec's privacy legislation. It was adopted in 2021 and its changes came into force in stages through 2024. According to the Commission's own pages:

| Topic | What the Commission says |
|---|---|
| 22 September 2023 | The Commission announced that certain Law 25 provisions entered into force that day |
| Governance | Organizations must have policies and practices on governing personal information and publish information about them in clear terms |
| Privacy impact assessment | Required when the law requires it, for example before communicating personal information outside Quebec. Also required for projects to acquire, develop or redesign an information system or electronic service delivery that involves personal information |
| Leaving Quebec | Since September 2023, before communicating personal information outside Quebec, an organization must conduct a privacy impact assessment. The communication may go ahead if the assessment shows the information would receive adequate protection, and it must be covered by a written agreement |
| Proportionality | The assessment must be proportionate to the sensitivity of the information, the purpose of its use, its quantity, its distribution and its medium |
| Consent | New rules on consent to collect, communicate or use personal information, including consent for each purpose in simple and clear terms |
| Privacy by default | For technology products or services offered to the public, default privacy settings must give the highest level of confidentiality without the person acting |

The assessment itself is your own analysis, ideally done with your advisers.

## What it means for teams sending prompts to AI providers

A prompt can contain personal information without anyone noticing. A pasted email thread, a support ticket, an HR note. If your provider processes that prompt outside Quebec, the rule about assessments is in play. A few practical questions follow from the regulator's wording:

1. **What personal information actually reaches providers?** You cannot assess what you cannot see.
2. **Which providers and which regions?** The assessment looks at where information goes and how it is protected.
3. **Is the use proportionate?** Sensitive information and large volumes call for more care.
4. **Can you show your work?** Governance and written agreements need evidence, not memory.

## How OpenProxyAI helps you answer those questions

OpenProxyAI is an open-source, self-hosted gateway. Your applications send every model call to one OpenAI-compatible endpoint, so what leaves your network passes through one place you control.

**See what is being sent.** Personal data detection scans prompts for emails, card numbers and ID numbers. Start in log-only mode: it records what it would catch and lets everything through, so you can measure real exposure. See [Policies and guardrails](/core-concepts/policies-and-guardrails).

**Block or reroute what should not leave.** In enforce mode, a request that breaks a rule stops before it reaches a provider and the caller gets a plain explanation. Each request also carries a data class, from public to secret. You choose which class a detected kind of personal data raises the request to, and callers can raise it by header but never lower it.

**Approve models per class.** A registry lists the models you have vetted. Each entry records the highest class the model may receive, its regions, a risk rating and its retention terms. In enforce mode, a request is served only by a model cleared for its class. A model you do not trust with personal information simply never receives it. See [Provider routing](/core-concepts/provider-routing).

**Keep the most sensitive traffic inside your network.** Provider keys can point to your own endpoint, such as a model running in your environment, and be marked as internal. Pair that with a registry entry cleared for your highest class, and your most sensitive prompts do not leave. See [Data residency](/security/data-residency) and [API keys and provider keys](/api-reference/keys).

**Keep the evidence.** Every request is logged with who called, which model and provider served it, the policy decision and the routing decision. Entries are written once and never edited, and an export is available for reviewers. These records can support your assessment file. See [Audit logging](/security/audit-logging).

## A worked scenario

A Montreal insurer wants an assistant that summarizes claim notes. Before launch, the team turns on personal data detection in log-only mode for two weeks. The report shows which kinds of personal data appear and in which applications. The team marks claim-note traffic as confidential, approves two vetted models for that class, and attaches an internal endpoint for the most sensitive notes. It switches to enforce. Now a developer who tries a new model that is not cleared gets a clear refusal, and the privacy officer has an audit export for the assessment file.

## What to do now

- Inventory which applications send prompts to providers.
- Run personal data detection in log-only mode and read the report.
- Define your data classes and decide which one personal information raises requests to.
- Approve models per class, and use an in-network model for the most sensitive class.
- Document your assessment with your advisers, and keep the audit export with it.
- Revisit the assessment when you add a provider or a model.

## Good to know

Region tags in OpenProxyAI use broad values (us, eu, ap and global). They help you keep traffic on provider keys and models tagged for a region, but they are not a Quebec-specific setting. For the strictest cases, rely on data classes and in-network models.

OpenProxyAI provides controls and records, not legal advice and not certification. Whether Law 25 applies to your organization and what your assessment must conclude are questions for your legal team.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If it helps, star the repo or open an issue with what your privacy office needs.

## Sources

- [Quebec government, published by the Commission d'accès à l'information, 22 September 2023: Loi 25, entrée en vigueur de dispositions](https://www.quebec.ca/nouvelles/actualites/details/loi-25-entree-en-vigueur-de-dispositions-qui-rehaussent-la-protection-de-la-vie-privee-des-quebecois-50719): the announcement and the main new obligations.
- [Commission d'accès à l'information: Principaux changements apportés par la Loi 25](https://cai.gouv.qc.ca/protection-renseignements-personnels/sujets-et-domaines-dinteret/principaux-changements-loi-25): leaving Quebec, assessments, consent, privacy by default.
- Related: [Data residency](/security/data-residency), [Policies and guardrails](/core-concepts/policies-and-guardrails), [Audit logging](/security/audit-logging).

These statements are based on the sources and on OpenProxyAI's behavior at the post date. This is not legal advice.
