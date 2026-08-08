---
title: Errors & Status Codes
description: Standard and OpenProxyAI-specific HTTP status codes, and the SDK exception types they map to.
---

# Errors & Status Codes

## Standard codes

| Code | Meaning |
|---|---|
| `200` | Success |
| `400` | Malformed request |
| `401` | Missing or invalid API key |
| `404` | Resource not found |
| `500` | Internal error |

## OpenProxyAI-specific codes

| Code | Meaning | SDK exception |
|---|---|---|
| `402` | Budget exceeded | `BudgetExceededError` |
| `429` | Rate limit hit (requests/min or tokens/min) | `RateLimitError` |
| `446` | Blocked by an enforcing policy | `PolicyViolationError` |

These map directly to the request pipeline stages that can reject a request — see [Request Pipeline](/core-concepts/request-pipeline).

## Provider-side errors

An error from the upstream provider itself (not from OpenProxyAI's own pipeline) surfaces as `ProviderError` in the SDKs, with the original provider identified so you can distinguish "OpenProxyAI blocked this" from "the model provider itself errored."

## Retry guidance

`BudgetExceededError` and `RateLimitError` both carry a `retry_after` (Python) / equivalent field indicating when to retry. `PolicyViolationError` is not retryable as-is — the request content itself needs to change, or the policy needs to be reconfigured (see [Policies & Guardrails](/core-concepts/policies-and-guardrails)).
