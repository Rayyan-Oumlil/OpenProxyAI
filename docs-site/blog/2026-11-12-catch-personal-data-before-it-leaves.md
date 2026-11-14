---
slug: catch-personal-data-before-it-leaves
image: /img/blog/og/catch-personal-data-before-it-leaves.png
title: "Catch personal data before it leaves: PII checks you can trust before you enforce"
tags: [security, product]
description: "Detect emails, card numbers and ID numbers in prompts before they reach a model provider. Start in log-only mode, move to enforce when the hits look right, and give users a refusal they can understand."
---

Someone pastes a customer email thread into a chat box. Someone else sends a support ticket with a card number to a summarizer. Nobody meant harm, and the personal data (often called PII, for personally identifiable information) is now at a third-party model provider. You cannot train every employee to never do this, and you cannot review every prompt by hand. What you can do is check each request on its way out. OpenProxyAI does this at the gateway, so every application gets the same protection without changing its code.

{/* truncate */}

![A request passes a personal data check. In log-only mode the hit is recorded and the request continues. In enforce mode the request stops at the gateway and the caller gets a 446 with a plain sentence.](/img/blog/catch-personal-data-before-it-leaves.svg)

## What gets detected

Detection runs on the text of each request, before anything is sent to a provider.

| Detector | What it finds |
|---|---|
| Built-in | Email addresses, US Social Security numbers written with separators, and payment card numbers that pass a checksum. |
| Optional, stronger | Adds names, phone numbers, IBANs and more, using the Presidio detection engine. You turn it on for your deployment. |

The checksum matters. A random 16-digit number, such as an order ID, is not flagged as a card unless it is a valid card number. That keeps false alarms down. Text is normalized before it is scanned, so simple tricks like extra spacing do not hide a value.

The same detector also feeds data classes. A request containing a card number is automatically raised to a higher class, which can limit which models may serve it. See [data classes](/blog/data-class-taxonomy-people-use).

## Log-only first, then enforce

The organization policy has one enforcement mode, and it applies to every check in the policy.

| Mode | What happens when personal data is found |
|---|---|
| Off | Nothing is checked. |
| Log-only | The hit is recorded in the audit log and the analytics, and the request goes through. |
| Enforce | The request is refused before it reaches any provider. |

Start in log-only. Run it on real traffic for a week and watch two numbers on the dashboard: requests the policy flagged, and requests it blocked. Flagged means "caught and allowed". When the flags look like real personal data and not noise, switch to enforce. The [managing policies](/admin-console/managing-your-organization) page describes the same pattern.

You can also try a request before changing anything. The console has a policy preview for admins that runs a made-up request through classification, the policy and routing, and shows what would happen, without sending anything to a provider or using budget.

## What a blocked request returns

In enforce mode the caller gets HTTP status 446, which the gateway uses for "blocked by policy". The body keeps technical fields for your code and adds one plain sentence for people. It looks like this (abbreviated):

```json
{
  "error": "policy_violation",
  "reason_code": "pii_detected",
  "explanation": "This request appears to contain personal or sensitive data that your organization's policy does not allow to be sent."
}
```

Use the reason code in code and show the explanation to the user. The sentence does not reveal what was matched, so it cannot be used to probe the rules. The Python and TypeScript SDKs raise a policy violation error for this status. See [refusals should explain themselves](/blog/refusals-should-explain-themselves).

A blocked request is not retryable as is. The user needs to remove the data, or an admin needs to change the policy.

## Block, not rewrite

For requests, enforce mode blocks. The gateway does not quietly remove the personal data and send the rest on. That is a deliberate choice: silently rewriting a prompt can change its meaning and give the user an answer to a question they did not ask. If you want requests with personal data to stop, this is the setting.

Answers are different. You can turn on response checks, so that a model answer containing personal data is withheld, or returned with the personal data replaced. The check runs before the answer is cached, so the cache holds what the caller saw. Tool call arguments sent through the MCP gateway are scanned too.

## A worked example

A support team uses an assistant that summarizes tickets.

1. The security lead turns on personal data detection in log-only mode.
2. After a week, analytics shows about one in forty tickets flagged. Most are email addresses in signatures.
3. The team decides emails are acceptable for this tool, but card numbers are not. They keep the policy on and plan to add the stronger detector for names.
4. They switch to enforce. An agent pastes a ticket with a card number. The assistant returns the plain refusal and the agent removes the number and resends.
5. The audit log has a record of the block and its reason, without the card number itself.

The numbers in this example are illustrative.

## What to do now

- Turn on detection in log-only mode today, on real traffic.
- Read the flagged and blocked counts for a week and sample the audit entries.
- Decide which kinds of data are never acceptable, and which are fine for which tools.
- Add the stronger detector if you need names, phone numbers or IBANs.
- Show your users the explanation sentence in your app, not a generic error.
- Switch to enforce, and tell users what a refusal means before they see one.
- If you use a compliance template, review the result afterward. It replaces your guardrail settings.

## Good to know

Policy checks run on the prompt text, so keep keyword lists specific. The built-in detector is intentionally narrow, to keep false alarms low. Enabling personal data detection requires a plan that includes it, and the Community plan does not. A request too large to scan completely is refused in enforce mode instead of being checked in part.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. Star the repo or open an issue if there is a kind of data you need detected.

## Sources

- [Policies and guardrails](/core-concepts/policies-and-guardrails): modes, checks, what is blocked, and response guardrails.
- [Managing policies](/admin-console/managing-your-organization): switching between log-only and enforce.
- [Errors and status codes](/api-reference/errors-and-status-codes): the 446 response and its explanation field.
- [Compliance templates](/security/compliance-templates): starting points and the detector they assume.
- [Request pipeline](/core-concepts/request-pipeline): where the policy check sits.

These statements are based on OpenProxyAI's docs and behavior as of November 12, 2026. OpenProxyAI ships templates and controls, not certifications, and using it does not make anyone compliant with a privacy law.
