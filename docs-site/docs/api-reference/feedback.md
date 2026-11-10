---
title: Feedback
description: POST /v1/feedback — tell the gateway whether an answer was good, using an API key.
---

# Feedback

```
POST /v1/feedback
```

Rate one answer. Your application sends this with the same API key it uses for chat, so no console login is needed. Ratings are stored as request scores, and for a request that ran in an experiment they are attached to its variant, which is what the experiment results and the evaluation features that follow it read.

## Which id to send

Every response from the gateway carries `x-openproxyai-request-id`. Keep it next to the answer you showed, and send it back with the rating.

The request log is written just after the response is returned, so a rating sent within the first moments can get a `404 request_not_found`. Retrying after a second works.

## Request

Send exactly one of `thumbs` or `value`.

```json
{
  "request_id": "373fec91-2bd8-4c1e-9826-7a365b5f9073",
  "thumbs": "down",
  "comment": "It ignored the second question."
}
```

```json
{
  "request_id": "373fec91-2bd8-4c1e-9826-7a365b5f9073",
  "score_name": "coherence",
  "value": 4.5
}
```

| Field | Required | Notes |
|---|---|---|
| `request_id` | yes | The `x-openproxyai-request-id` of the request being rated. Dashes are optional. |
| `thumbs` | one of | `"up"` is stored as `1`, `"down"` as `0`, so the mean of a thumbs score is a satisfaction rate. The score name defaults to `thumbs`. |
| `value` | one of | A number between -999999 and 999999. Needs a `score_name`. |
| `score_name` | with `value` | Letters, digits and `_ . : -`, up to 100 characters. |
| `comment` | no | Up to 2000 characters. Anything the PII detector finds (email addresses, SSNs, card numbers) is replaced with `[REDACTED]` before it is stored. |

Unknown fields are rejected with a 422, so a misspelled field name is not silently ignored.

## Response

```json
{"request_id": "373fec91-2bd8-4c1e-9826-7a365b5f9073", "score_name": "thumbs", "value": 0.0}
```

Sending the same `score_name` for the same request again replaces the earlier rating, so a user who changes their mind updates one row.

## Errors

| Status | `error` | Meaning |
|---|---|---|
| 401 | | Missing or invalid API key. |
| 403 | `missing_permission` | The key lacks the `proxy:llm` permission. |
| 404 | `request_not_found` | No such request in your organization. A request that belongs to another organization gets the same answer, so a key cannot probe for ids. |
| 422 | | The body is malformed (both or neither of `thumbs` and `value`, a bad name, a value out of range, an unknown field). |

## Who can rate what

Any API key with `proxy:llm` in your organization can rate any request in that organization. A key can therefore skew scores for the organization's own traffic. If feedback is going to come from untrusted end users, send it from your own backend and not from the browser.
