---
title: Policies & Guardrails
description: "The organization policy that checks every request and response: model allowlist, blocked keywords, PII, prompt-injection detection, and what a request gets back when one fires."
---

# Policies & Guardrails

Each organization has **one policy**. It runs against every request at the policy stage of the pipeline (see [Request Pipeline](/core-concepts/request-pipeline)) and, if you turn it on, against every response. There are no named policies to select per request. The policy is configured for the organization and applies to all of its traffic.

## Three modes

`enforcement_mode` is one setting for the whole policy:

| Mode | A check that fires |
|---|---|
| `off` | Nothing is checked. |
| `log_only` | The hit is recorded in the audit log and analytics, and the request goes through. Use it to see a new rule's false-positive rate before it blocks anything. |
| `enforce` | The request is refused with HTTP `446` and a plain-language `explanation`. |

## What is checked on a request

The checks run in this order. The first one that fires decides the outcome.

| Check | Setting | Reason code | What it does |
|---|---|---|---|
| Model allowlist | `allowed_models` | `model_not_allowed` | If the list is not empty, the requested model must be on it (exact match). An empty list means no restriction. |
| Blocked keywords | `blocked_keywords` | `blocked_keyword` | Case-insensitive substring match against the text of the request. The first match wins. |
| PII | `pii_detection_enabled`, `pii_entities` | `pii_detected` | Finds personal data in the request. The built-in detector finds email addresses, US Social Security numbers written with separators, and payment card numbers that pass a checksum. The optional Presidio detector adds names, phone numbers, IBANs and more. |
| Prompt injection | `prompt_injection_detection_enabled` | `prompt_injection_detected` | Scores the request with a classifier when the ML model is installed, and with regular expressions when it is not. If the classifier is unavailable or times out, the request is allowed. |
| Too large to scan | | `request_too_complex` | A request with more fields than the scanner will walk is refused in `enforce` mode, not scanned in part. |

Organizations can also add their own checks as [policy plugins](/guides/policy-plugins), and the [MCP gateway](/guides/mcp-gateway) applies tool allow and block lists to tool calls.

In `enforce` mode, PII in a request **blocks** it. The gateway does not rewrite the request and send the rest on. If you want requests with personal data to stop, this is the setting; if you want them redacted, the policy does not do that for requests.

## What is checked on a response

Turn on `response_guardrails_enabled` to check what the model sends back:

- A response containing a blocked keyword is withheld in `enforce` mode (`response_keyword_blocked`).
- A response containing PII is withheld, or, with `response_pii_redact` on, returned with the personal data replaced.

Response checks run before the answer is written to the [cache](/core-concepts/caching), so a cached answer is the one the caller saw.

## Setting the policy

Read and change the policy at `/api/v1/organizations/current/policy`. A `PATCH` takes only the fields you send:

```bash
curl -X PATCH https://gateway.your-company.com/api/v1/organizations/current/policy \
  -H "Authorization: Bearer $ADMIN_JWT" -H "Content-Type: application/json" \
  -d '{"enforcement_mode": "log_only", "blocked_keywords": ["internal use only"], "pii_detection_enabled": true}'
```

Other settings live on the same policy and are covered in their own pages: routing and the model registry, data classes, MCP tool lists, behavior defaults and ceilings, payload capture, and conversations. The console's Policy page is a view over the same configuration. See [Managing Policies](/admin-console/managing-your-organization).

## Starting from a template

Three [compliance templates](/security/compliance-templates) set the guardrail fields in one call. They are starting points, not certifications. Applying one needs a plan that includes PII detection; the Community plan does not.

## Viewing policy activity

Policy hits are queryable at `/api/v1/analytics/policy` and exportable at `/api/v1/analytics/policy/export`.
