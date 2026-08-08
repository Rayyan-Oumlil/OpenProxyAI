---
slug: compliance-templates-not-badges
title: "Compliance templates: policy configs, not badges"
authors: [rayyan]
tags: [product, security]
description: We shipped Healthcare, Finance, and Government policy templates this phase. Here's exactly what that means, and — just as importantly — what it doesn't.
---

We shipped three compliance templates this phase — Healthcare, Finance, and Government — and the most important thing to say about them is what they're *not*: they're not a claim that OpenProxyAI holds any certification on your behalf. They're pre-built policy configurations you apply, review, and enforce yourself.

{/* truncate */}

## Why the distinction matters

It's common in this category to see a security page with a row of certification badges and fine print that, read carefully, describes a much narrower claim than the badge implies. We'd rather not do that. If you're evaluating OpenProxyAI for a regulated workload, the honest starting point is: **we don't currently hold SOC 2, ISO 27001, or HIPAA certification.** Full detail on where things actually stand is on the [Trust Center](/security/trust-center).

What we do have is a real, useful thing that's easy to describe accurately: three starting configurations that encode the policy decisions a Healthcare, Finance, or Government deployment usually needs to make anyway.

## What's actually in each one

**Healthcare** sets PHI redaction defaults tuned for clinical data, restricts which models can receive requests tagged as containing clinical content, and extends audit retention beyond the platform default.

**Finance** blocks cardholder-data patterns before they reach a provider, captures transaction context in the audit log, and tightens default rate limits.

**Government** pairs with air-gapped deployment (`AIRGAP_MODE=true`) and enforces data residency with no fallback outside approved regions, plus 7-year audit retention.

## Applying one doesn't lock you in

A template merges into your organization's existing policy configuration — it doesn't overwrite what you've already customized, and nothing about applying one prevents you from adjusting individual policies afterward. Turn a policy from `enforce` to `log-only` while you evaluate its false-positive rate. Tighten a threshold. Swap the model allowlist. The template is a starting point calibrated to a framework's typical requirements, not a fixed configuration you're stuck with.

## The honest pitch

If your actual requirement is "we need a SOC 2 report to show our auditor," a policy template doesn't satisfy that — no software can, that's an organizational process, not a config file. What it does do: it gets you from a blank policy configuration to something aligned with what your framework typically requires, in one API call instead of reading the framework's requirements document and building each policy from scratch.

See [Compliance Templates](/guides/compliance-templates) for how to apply one, and the [Trust Center](/security/trust-center) for where our own certification status actually stands today.
