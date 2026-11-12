---
title: Realtime (WebSocket)
description: The OpenAI Realtime API through the gateway, with policy, limits, billing and revocation applied to a live session.
---

# Realtime

`WS /v1/realtime?model=openai/gpt-4o-realtime-preview`

You speak the provider's own Realtime protocol; the gateway sits in the middle. Only OpenAI is supported.

## Connecting

Authenticate with your gateway key (`opai_...`), either way:

| From | How |
|---|---|
| A server or SDK | `Authorization: Bearer opai_...` |
| A browser (cannot set headers) | WebSocket subprotocols `realtime` and `openai-insecure-api-key.opai_...` |

A key in the URL is **not** accepted: URLs end up in logs. A missing or wrong key is refused before the connection opens (HTTP 403).

After the connection opens, a refusal is a close with a code and a reason:

| Close | Reason |
|---|---|
| 1008 | `only_openai_is_supported`, `model_must_be_provider_slash_name`, `policy_blocked:<code>`, `rate_limited:<limit>`, `too_many_realtime_sessions`, `response_guardrails_not_supported_in_realtime`, `realtime_disabled` |
| 1008 | `credentials_no_longer_valid` (key revoked, user deactivated or key expired, or the policy now refuses the model), `session_time_limit` |
| 1009 | `message_too_large` |
| 1003 / 1007 | binary frame / not a JSON event |
| 1008 | `provider_unavailable`: no key of yours could open the provider's session |
| 1011 | `internal_error` |

## What the gateway does to a session

- **Policy on what you send.** Every text you put in an event (`session.update` instructions, `conversation.item.create` content and function output, `response.create` instructions) goes through your organization's policy. A refused event is **not** forwarded; you get an `error` event with `code: "policy_violation"` and the session continues. Audio is not readable, so the session is classified as uninspected input (confidential unless your class map says otherwise).
- **Only known events.** Client events outside the Realtime protocol's list are answered with `error` / `unsupported_event` and not forwarded.
- **Limits on each response.** Every `response.create` is checked against your rate and budget limits first; if refused you get `error` / `limit_exceeded` and no response starts.
- **Billing per response.** Each `response.done` is priced from the usage the provider reports (audio and text tokens at their own rates) and written to the request log as its own row (`modality: realtime`). If the breakdown is missing or inconsistent, every token is charged at the dearer audio rate; an unpriced model is charged `UNPRICED_CALL_COST_USD`. If a response cannot be recorded, the session ends.
- **Your key is not the provider's key.** The provider is opened with your organization's provider key. Keys with a custom endpoint are not used for realtime.
- **Revocation.** Every `REALTIME_CHECK_SECONDS` (default 30) the gateway re-checks the key, user and policy. A revoked key ends the session within that window; a newly tightened policy applies to the next message once the cached policy refreshes (up to a minute).

## Not supported

- **Response guardrails.** The answer streams out as it is spoken and cannot be held back, so an organization with `response_guardrails_enabled` under `enforce` cannot use realtime (rather than have its guardrail silently skipped).
- Providers other than OpenAI; binary frames; custom provider endpoints.

## Settings

`REALTIME_ENABLED`, `REALTIME_MAX_SESSION_SECONDS` (3600), `REALTIME_MAX_MESSAGE_BYTES` (1 MiB), `REALTIME_MAX_SESSIONS_PER_ORG` (20), `REALTIME_CHECK_SECONDS` (30). See [Environment flags](/getting-started/environment-flags).
