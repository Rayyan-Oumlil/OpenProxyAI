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
| `402` | A streamed request whose estimated cost is more than the remaining daily budget (`budget_exceeded`) | `BudgetExceededError` |
| `429` | A rate or budget limit was reached. The body's `limit_type` says which; see [Rate limiting & budgets](/core-concepts/rate-limiting-and-budgets) | `RateLimitError` |
| `446` | Blocked by an enforcing policy | `PolicyViolationError` |

These map directly to the request pipeline stages that can reject a request — see [Request Pipeline](/core-concepts/request-pipeline).

### What a `446` body contains

A `446` body keeps its technical fields (`error`, `reason_code`, `detail`, and for routing refusals `route_reason`, `data_class` and `requested_model`) and adds one more:

| Field | What it is |
|---|---|
| `explanation` | One plain sentence you can show an end user: what was refused and why. |

```json
{
  "error": "routing_blocked",
  "reason_code": "no_authorized_model",
  "detail": "No model authorized for this request's data class can serve it.",
  "explanation": "openai/gpt-4o is not approved for confidential data in your organization."
}
```

The sentence names only what the caller already knows: the model they asked for and the data class of their own request. It never says which keyword, pattern, plugin or registry setting was involved, and it does not distinguish a disabled model from one with no usable key. Use `reason_code` in code; show `explanation` to people. The same sentence appears on the request trace and in the policy preview in the console.

## Provider-side errors

An error from the upstream provider itself (not from OpenProxyAI's own pipeline) surfaces as `ProviderError` in the SDKs, with the original provider identified so you can distinguish "OpenProxyAI blocked this" from "the model provider itself errored."

## Retry guidance

`BudgetExceededError` and `RateLimitError` both carry a `retry_after` (Python) / equivalent field indicating when to retry. `PolicyViolationError` is not retryable as-is — the request content itself needs to change, or the policy needs to be reconfigured (see [Policies & Guardrails](/core-concepts/policies-and-guardrails)).
