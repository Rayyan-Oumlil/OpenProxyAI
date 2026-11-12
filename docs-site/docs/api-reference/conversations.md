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
| `POST` | `/` | Start one. Body: `{"title", "visibility": "private"\|"team"\|"org", "team_id", "tags", "system_prompt", "space_id"}`. A `private` tag cannot be combined with sharing (422 `private_tag`). A `space_id` must be a space you can see (422 `space_not_available`). `org` is admin only (403 `admin_only`). Sharing needs a team you belong to (422 `not_a_team_member`). 403 `conversations_disabled`; 409 `too_many_conversations` at 500. |
| `GET` | `/?scope=mine\|shared\|org&tag&q&space_id&limit&offset` | List. `org` is admins only and returns titles, owners and sizes. `tag` is an exact tag. `q` is text in a title or a tag; message content is never searched. `space_id` lists what is filed in that space (and only what you could read anyway). |
| `GET` | `/{id}` | One conversation. 404 if it is not yours or not shared with you. |
| `GET` | `/{id}/turns` | The messages, in order, with each one's `data_class` and `model`. |
| `PATCH` | `/{id}` | Owner only: `title`, `tags`, `space_id` (`null` takes it out of its space), `visibility`/`team_id`. Only what you send changes; going private clears the team. Adding the `private` tag makes it private. |
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

## Tags

Up to 10 per conversation, at most 30 characters each: letters, digits and `. # + / - _`, with single spaces inside. They are trimmed, lower-cased and de-duplicated; anything else (a comma, a newline, markup) is a 422.

The tag `private` is special. A conversation that carries it cannot be shared: creating or updating it with `visibility` `team` or `org` is refused (422 `private_tag`), and adding the tag to a conversation that is already shared makes it private again and clears its team. Removing the tag does not share anything.

## Spaces

```
/api/v1/spaces
```

A space is a named folder for finding conversations. **It never changes who can read one.** A space is visible to its owner and, if it has a team, to that team's members (an admin is not special here). Listing a space shows only the conversations you could already read, and every conversation route keeps its owner, team and visibility rule.

| Method | Path | |
|---|---|---|
| `POST` | `/` | Create. Body: `{"name", "team_id"}`. `name` is 1 to 100 characters, unique per owner ignoring case (409 `space_name_taken`); `team_id` must be a team you belong to (422 `not_a_team_member`). At most 50 per user (409 `too_many_spaces`). Needs conversations enabled for the org. |
| `GET` | `/` | The spaces you can see: yours and your teams'. Each has `conversation_count`, which counts only conversations you can read. |
| `PATCH` | `/{id}` | Owner only: `name`, `team_id` (`null` makes it personal). 404 for anyone else. |
| `DELETE` | `/{id}` | Owner only. The space's conversations are not deleted; they leave the space. 204. |

A conversation response includes `space_id` and `space_name` only when you can see that space. Deleting a team turns its spaces personal.
