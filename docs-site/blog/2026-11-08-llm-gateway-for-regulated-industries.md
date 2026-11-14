---
slug: llm-gateway-for-regulated-industries
image: /img/blog/og/llm-gateway-for-regulated-industries.png
title: "An LLM gateway for regulated teams: HIPAA, PCI, FedRAMP and the EU AI Act"
tags: [security, product]
description: "How an LLM gateway gives HIPAA, PCI DSS, FedRAMP-aligned and EU AI Act teams enforceable controls and audit evidence for AI traffic, and what the compliance templates in OpenProxyAI set for you."
---

If you work in healthcare, payments, the public sector or the EU, you probably have a version of the same problem. Teams are already sending prompts to model providers, and those prompts leave your network. When an auditor asks who sent what, to which model, and what was blocked, the honest answer is often "we would have to check each app". An LLM gateway puts one checkpoint in front of every provider, so the answer becomes a query instead of a project. This post maps four regimes to the controls that help, and shows what that looks like in OpenProxyAI.

{/* truncate */}

![Prompts from regulated apps pass through one gateway that checks identity, content, model and region, then logs the decision](/img/blog/llm-gateway-for-regulated-industries.svg)

## The problem every regulated team shares

Each regime asks for different paperwork, but the day-to-day risk is the same four things:

- **Content leaves.** A clinician pastes a note, or an agent pastes a card number.
- **Nobody sees the whole picture.** Each app has its own key and its own logging, if any.
- **Model choice is ad hoc.** Any team can point at any model in any region.
- **Evidence is scattered.** Proving a control existed last quarter means digging.

A gateway does not fix your policies. It gives you one place where policies are enforced and recorded. You can read more about why in [why every company needs an LLM gateway](/blog/why-every-company-needs-an-llm-gateway) and [shadow AI needs a governed front door](/blog/shadow-ai-needs-a-governed-front-door).

## Which controls help with which regime

This table is a map of controls, not a statement that any control satisfies a regime. Your compliance team decides what counts.

| Regime | What it is about | Gateway controls that help | Starting template |
|---|---|---|---|
| HIPAA | Protecting health information and the vendors who handle it | PII and keyword guardrails in enforce mode, model allowlists, append-only audit log, SSO and SCIM so access follows your directory | Healthcare |
| PCI DSS | Protecting payment card data | Card-number detection that blocks in enforce mode, keyword guardrails, audit log and compliance export, row-level security between tenants | Finance |
| FedRAMP-aligned | Cloud services used by US federal agencies | Classification-marking keywords, data residency, model allowlists, audit log, SSO and SCIM | Government |
| EU AI Act | Rules for AI systems, including logging for high-risk uses | Data residency, model allowlists, audit log with retention by plan, exportable evidence | None, use the base policy |

### The controls in plain words

- **PII and keyword guardrails in enforce mode.** The gateway checks each prompt. If it finds a match, the request is refused with a clear reason (HTTP 446) instead of reaching the provider. In log-only mode the same hit is recorded and the request goes through, which is how you measure before you block.
- **Model allowlists.** Only the models you approve can be called.
- **Data residency.** Each organization has one data region, and the gateway only uses provider keys and models tagged for it, even during failover. See [data residency](/security/data-residency).
- **Append-only audit log.** One record per request, plus a record of every administrative change. See [audit logging](/security/audit-logging) and [an audit trail your auditor can read](/blog/an-audit-trail-your-auditor-can-read).
- **Retention by plan.** Request logs are kept from 7 days on Community up to 365 days on Enterprise. If you need longer, export on a schedule or stream to your SIEM.
- **SSO and SCIM.** People sign in with your identity provider, and joiners and leavers flow in automatically. See [SSO and SCIM for AI access](/blog/sso-and-scim-for-ai-access).
- **Row-level security.** Tenant isolation is enforced in the database. See [row-level security by construction](/blog/row-level-security-by-construction).

## The compliance templates

OpenProxyAI ships three templates, for healthcare, finance and government. Applying one fills in the guardrail settings of your organization policy in a single admin call: enforcement turned on, a keyword list, a list of personal-data types to detect, prompt-injection detection, and redaction of personal data in responses.

| | Healthcare | Finance | Government |
|---|---|---|---|
| Keywords include | diagnosis, medical record, prescription | account number, routing number, wire transfer | classified, top secret, controlled unclassified |
| Personal data detected includes | names, SSNs, dates of birth, medical license numbers | card numbers, bank numbers, IBANs | passport numbers, IP addresses, locations |

Applying one replaces your keyword list, keeps your model allowlist, limits and routing, and turns on enforcement immediately. So apply it in a staging organization, or switch to log-only straight away in production and review the hits first. Details are in [compliance templates](/security/compliance-templates) and [compliance templates, not badges](/blog/compliance-templates-not-badges).

## A worked scenario

A regional health network wants clinicians to use an AI assistant for drafting patient letters. The platform lead sets it up in one afternoon.

1. They connect SSO so every request is tied to a named clinician, and SCIM so leavers lose access the same day.
2. They apply the healthcare template in log-only mode and let a week of real traffic flow. The audit log shows which keywords fire on harmless text, such as an engineer asking about a field called "diagnosis". They trim the list.
3. They set the organization region to the EU and tag their provider keys and registered models to match. A request can no longer reach an out-of-region model, even when the primary provider is down.
4. They restrict the allowlist to the two approved models and switch the policy to enforce.
5. The first time a clinician pastes a note with a patient name and a date of birth, the gateway returns a refusal that says why. The event is in the audit log with a request id.
6. At the annual review, the compliance lead exports the policy events and the admin change history as CSV and attaches them to the assessment.

At no point did the lead edit the clinical app. The controls sat in front of it.

## What to do now

- List every app and script that calls a model provider directly, and move them behind one endpoint.
- Decide your data region and tag keys and models honestly.
- Apply the closest template in log-only mode, review a week of hits, then enforce.
- Turn on SSO and SCIM so access follows your directory.
- Schedule an export of the audit data that matches your retention needs.

## Good to know

A gateway gives you controls and evidence. The agreements and judgments around them stay with your organization, and that is a feature: your auditor expects a human owner for each.

- **Provider agreements still apply.** If a provider will handle protected health information for you, HIPAA expects a written business associate agreement in place. The rule says a covered entity may disclose protected health information to a business associate only after obtaining satisfactory assurance, documented in a written contract or other written agreement (45 CFR 164.502(e)). Sign the agreement with your provider, then use the gateway to make sure only approved models see that traffic.
- **Your risk assessment still matters.** The gateway tells you what it blocked and recorded. Deciding what is acceptable is yours.
- **Match rules are specific by design.** Keyword matching is a plain substring check and the personal-data detector looks for defined types, so keep lists specific and test in log-only first. Free text that matches neither is not caught.
- **Regimes keep moving.** For a deeper read, see [HIPAA and LLMs](/blog/hipaa-and-llms), [the PCI SSC guidance on AI](/blog/pci-ssc-ai-guidance-agents-cardholder-data), [FedRAMP 20x and AI](/blog/fedramp-20x-ai-and-consolidated-rules) and [the EU AI Act for engineers](/blog/eu-ai-act-for-engineers).

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

This needs Docker and no provider key. The console is at http://localhost:5173. If it is useful, star the repo or open an issue with the control your regime needs most.

## FAQ

### Does a gateway make me HIPAA compliant?

No. A gateway provides controls and evidence. Compliance is your organization's responsibility and covers policies, training, agreements and risk analysis that no tool can do for you.

### Are the compliance templates certifications?

No. They are starting guardrail settings that you apply, test and enforce yourself. OpenProxyAI does not claim HIPAA, PCI DSS or FedRAMP certification or authorization, and applying a template does not give you one.

### Can I keep prompts inside one region?

Yes, for traffic that goes through the gateway. You set one region per organization and tag provider keys and models. Requests only use matching ones, including on failover. The gateway trusts your tags, so tag honestly, and deploy the gateway itself in the region you need.

### Does it help with EU AI Act logging?

It helps you keep records. The Act requires high-risk AI systems to technically allow automatic recording of events, and requires deployers of such systems to keep the logs they control for a period appropriate to the purpose, of at least six months (Articles 12 and 26). Whether your system is high-risk is a legal question for you. The audit log and exports give you the raw records, and you choose the retention that fits.

### Which personal data is detected out of the box?

Email addresses, US Social Security numbers written with separators, and payment card numbers that pass a checksum. Names, phone numbers and other types need the optional detector.

## Sources

- [45 CFR 164.502, uses and disclosures of PHI, eCFR](https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164/subpart-E/section-164.502): business associate assurances, paragraph (e).
- [PCI SSC press release, 7 October 2026](https://www.pcisecuritystandards.org/about_us/press_releases/pci-ssc-publishes-additional-guidance-on-securing-ai-in-payment-environments/): the AI guidance is not mandatory, and PCI standards take precedence over it.
- [EU AI Act, Article 12](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-12) and [Article 26](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-26): record-keeping and deployer log retention, European Commission AI Act Service Desk.
- [FedRAMP 20x](https://www.fedramp.gov/20x/): FedRAMP describes a government-wide, standardized, reusable approach to cloud security assessment and authorization.
- Docs: [compliance templates](/security/compliance-templates), [data residency](/security/data-residency), [audit logging](/security/audit-logging), [policies and guardrails](/core-concepts/policies-and-guardrails), [trust center](/security/trust-center).

These statements are based on the sources above and on OpenProxyAI's behavior at the post date.
