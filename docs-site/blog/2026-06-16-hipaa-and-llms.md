---
slug: hipaa-and-llms
title: "HIPAA and LLMs: what 'compliant' actually requires from your AI infrastructure"
authors: [rayyan]
tags: [security, product]
description: HIPAA-compliant AI gets used as a marketing phrase more often than a technical one. Here's what actually has to be true about your infrastructure before that phrase means anything.
---

"Is this HIPAA compliant?" is one of the first questions a healthcare buyer asks about any AI tool, and it's also one of the most commonly answered wrong — not maliciously, just imprecisely. HIPAA compliance isn't a property a piece of software has on its own. It's a property of how an organization uses that software, backed by specific technical and contractual controls.

{/* truncate */}

## The BAA is the actual gate, not the feature list

Before anything else: if a vendor is going to touch Protected Health Information (PHI), you need a signed Business Associate Agreement (BAA) with them. No BAA means no PHI should be flowing to that vendor, full stop, regardless of how good their security page looks. This is a contractual requirement, not a technical one — and it's the single most common gap between "we use AI tools" and "we use AI tools in a HIPAA-compliant way" at healthcare organizations.

Most frontier model providers now offer a BAA path (usually on their enterprise/business tiers, not the consumer product). Confirming that BAA is in place, and that it actually covers the specific product surface you're using, is step zero — before any conversation about redaction or logging.

## What has to be true technically

- **Minimum necessary.** PHI sent to a model should be the minimum needed for the task, not a full record dumped into context because it was convenient. This is a judgment call your team has to make per use case — infrastructure can help by making redaction easy to apply, but it can't decide what's "necessary" for you.
- **PHI redaction where the use case allows it.** A lot of LLM use cases (summarization, classification, drafting) don't actually need real patient identifiers in the prompt — a redacted or pseudonymized version works identically for the model's task. Where that's true, redacting before the request leaves your network reduces exposure even if the BAA is in place; belt and suspenders.
- **Audit logging.** HIPAA's Security Rule requires audit controls — the ability to show who accessed what PHI, when. For an AI system, that means every request touching PHI needs to be logged with enough detail (user, timestamp, what was accessed) to answer an auditor's question months later, not just "we have logs somewhere."
- **Access controls.** Role-based access so that only people with a legitimate need can see PHI-containing requests and logs — not just at the application layer, but enforced at the data layer too, so a misconfigured query can't accidentally surface another patient's data.
- **Retention and disposal.** PHI has retention requirements that cut both ways — data needs to be retained long enough to meet regulatory and audit needs, and disposed of appropriately once that requirement ends. "We log everything forever" isn't automatically safer; it's a growing liability surface.

## What "HIPAA-compliant infrastructure" can and can't do for you

Infrastructure can make the technical controls available and easy to turn on correctly: redaction defaults tuned for clinical data, an audit log that's actually queryable by an auditor, retention policies you can configure instead of hand-roll. What it can't do is make the compliance decision for you — whether a specific use case needs redaction, what counts as "minimum necessary" for a given workflow, whether your BAA coverage extends to a new feature you just enabled. That's why a template is a starting point, not a certificate: it's aligned to the requirements, but your organization's audit still runs against your organization's actual controls and decisions, not a vendor's marketing claim.

The honest short version: HIPAA compliance is an organizational commitment that infrastructure can support and make dramatically easier — a system with PHI redaction, immutable audit logs, and access controls built in saves real engineering time versus building those from scratch — but the BAA, the minimum-necessary judgment calls, and the retention policy are decisions your organization makes, not features a vendor ships.
