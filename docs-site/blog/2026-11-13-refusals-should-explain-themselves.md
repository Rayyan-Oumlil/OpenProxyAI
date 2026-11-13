---
slug: refusals-should-explain-themselves
title: "A refusal should say why in one sentence, and never say too much"
tags: [product, security]
description: A gateway that blocks a request owes the person behind it an answer. It also must not teach them how to get around the rule. Here is where we drew that line.
---

When a gateway refuses a request, two people are waiting on the answer. The developer wants a machine-readable reason. The person who typed the prompt wants to know what to do next. Most gateways serve only the first one: a status code, a reason string, maybe a rule name.

{/* truncate */}

## Why the rule name is the wrong thing to show

A reason like `blocked_keyword:acme-merger` tells a developer exactly what happened. Shown to an end user, it tells them which word to rewrite. A refusal that names the pattern is a hint for evasion, and one that names the policy plugin or registry setting leaks how your controls are built.

So an OpenProxyAI refusal carries two separate things:

- **`reason_code`** for the developer and the audit log: stable, specific, never shown to users by default.
- **`explanation`** for the end user: one plain sentence.

## What the sentence may contain

An explanation uses only what the caller already knows: the model they asked for and their request's own data class. For a routing refusal: "openai/gpt-4o is not approved for confidential data in your organization." For a policy block it says the category in general words ("This request contains wording that your organization's policy does not allow") and nothing more. It never names the keyword, the pattern, the plugin or the registry setting that decided. How the organization wired its registry (a disabled model, a missing key) is deliberately collapsed into one answer: "not available to your organization right now."

That rule is testable, and tested: every policy reason code must have a sentence, the sentences must name no rule detail, and the model name echoed back is bounded to one short line.

## Where it shows up

- Every `446` response includes `explanation` beside the existing fields, which are unchanged.
- The request trace in the console shows what the caller was told, next to the real reason.
- The policy preview shows what a caller would be told before you turn a rule on, so you can read your own refusals the way a user will.
- Both SDKs expose it as `PolicyViolationError.explanation`.

## Why 446

Policy blocks use HTTP 446, not 403. A 403 should mean "you are not authorized," which is a different problem with a different fix: a key without a permission is an access-control question, while a prompt that contains a card number is a data question. Keeping them apart makes dashboards, alerts and client retry logic honest.

## What it does not do

The explanation is one sentence, so it cannot say how to fix the request. It also cannot be translated by the gateway; applications that serve other languages should map `reason_code` to their own text and treat `explanation` as the fallback.
