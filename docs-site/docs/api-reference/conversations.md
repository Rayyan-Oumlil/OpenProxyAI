---
title: Conversations
description: /api/v1/conversations — keep a conversation in the gateway and send each model only the history it is cleared for.
---

# Conversations

```
/api/v1/conversations
```

Authenticated with a user JWT (the console's session). Read the [guide](/guides/conversations) first for what the gateway does with history. Requires `conversations_enabled` in the org policy to create conversations or add messages; a viewer can read what a teammate shared but cannot write.

## Endpoints

| Method | Path | |
|---|---|---|
| `POST` | `/` | Start one. Body: `{"title", "visibility": "private"\|"team", "team_id", "tags"}`. Sharing needs a team you belong to (422 `not_a_team_member`). 403 `conversations_disabled`; 409 `too_many_conversations` at 500. |
| `GET` | `/?scope=mine\|shared\|org&limit&offset` | List. `org` is admins only and returns titles, owners and sizes. |
| `GET` | `/{id}` | One conversation. 404 if it is not yours or not shared with you. |
| `GET` | `/{id}/turns` | The messages, in order, with each one's `data_class` and `model`. |
| `PATCH` | `/{id}` | Owner only: `title`, `tags`, `visibility`/`team_id`. Only what you send changes; going private clears the team. |
| `DELETE` | `/{id}` | Owner, or an admin (audited as `conversation.deleted`, without content). 204. |
| `GET` | `/teams` | Teams you belong to (the only ones you can share with). |
| `GET` | `/models` | Enabled registry models with a live key and the most sensitive class each may receive. |
| `POST` | `/{id}/turns` | Add a message and get the answer. Owner only. |
| `GET` | `/{id}/turns/{turn_id}/context` | What was sent for an answer. Anyone who can read the conversation. |

## Add a message

```bash
curl -X POST https://your-gateway/api/v1/conversations/$ID/turns \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"content": "Summarise it", "model": "openai/gpt-4o", "data_class": "confidential"}'
```

| Field | |
|---|---|
| `content` | 1–20,000 characters, not blank. |
| `model` | `provider/name`. Capability routes (`cap:...`) are not accepted here. |
| `data_class` | Optional. `public`, `internal`, `confidential` or `secret`. Can only raise the class. |
| `system_prompt` | Optional, up to 4,000 characters. Not stored; it is classified and policy-checked like the message. |
| `temperature`, `max_tokens` | Optional. |
| `max_context_tokens` | Optional budget for history (default 24,000 estimated tokens). |

Unknown fields are rejected (422).

**201** returns the stored `user_turn` and `assistant_turn`, token counts and cost, and a `context` object:

```json
{
  "context": {
    "package_id": "…", "model": "anthropic/claude-3-5-sonnet", "data_class": "internal", "routing_mode": "enforce",
    "included_turn_ids": [],
    "withheld": [
      {"turn_id": "…", "seq": 1, "reason": "above_clearance"},
      {"turn_id": "…", "seq": 2, "reason": "above_clearance"}
    ],
    "estimated_tokens": 14, "payload_sha256": "…", "outcome": "ok"
  }
}
```

`reason` is `above_clearance` (more sensitive than the model is cleared for) or `over_budget` (left out to fit `max_context_tokens`).

## Errors

| Status | `detail.error` | Meaning |
|---|---|---|
| 403 | `conversations_disabled` | The org has not turned conversations on. |
| 404 | | Not your conversation, not shared with you, or another org's. |
| 409 | `turn_in_progress` | An earlier message in this conversation is still being answered. |
| 422 | | Invalid input (or `not_a_team_member`). |
| 429 | `rate_limit_exceeded` | Counted on the whole package, not only the new message. |
| 446 | `refused` | Policy or routing refused: the message (or system prompt) is above the model's clearance, the model is not in the registry, or a policy rule matched. Nothing was sent or stored. |
| 502 | `model_error` | The provider call failed. Nothing was stored; `package_id` points at the record of what was sent. |

See also [errors and status codes](/api-reference/errors-and-status-codes).
