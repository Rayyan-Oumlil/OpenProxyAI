---
title: Conversations
description: Keep a conversation in the gateway, switch models mid-way, and let the gateway decide which earlier messages each model may see.
---

# Conversations

Most gateways are stateless: your application sends the whole history on every call. OpenProxyAI can keep the conversation for you, and that matters for one reason. **History is data too.** If message 3 contained something confidential and the user switches to a model that is only cleared for internal data on message 4, sending the whole history would hand that model the confidential text, even though message 4 on its own was harmless. Classification-aware routing (the model registry and `routing_mode`) stops one request reaching the wrong model; conversations stop *history* doing it.

It is **off by default**, because it is the first feature that stores what users said on purpose.

## Turn it on

```bash
curl -X PATCH https://your-gateway/api/v1/organizations/current/policy \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"conversations_enabled": true}'
```

In the console it is a checkbox on **Policy → Evaluation → Conversations**. Turning it off stops new conversations and messages. Existing conversations stay readable and can be deleted.

## What happens on each message

1. The new message is **classified**: the org default, raised by detected personal data, or by the class you assert (an assertion can only raise it).
2. The gateway looks up the **chosen model's clearance** in the model registry: the lower of the registry entry's class and its key's class.
3. It builds the **context**: earlier exchanges the model is cleared for, newest first, up to a token budget. Anything above the clearance is **held back**.
4. The package (system prompt, kept history, new message) is classified as a whole and goes through the **same policy and routing check as any request**. So even a bug in step 3 could not send a model data above its clearance: routing would refuse it.
5. The model is called through the normal path (key choice, metering, audit log, tagged `source: conversation`).
6. On success the exchange is stored, redacted. A **context record** says which earlier messages were sent and which were held back, and why.

The response tells you what was held back, so an answer that seems to have lost context is explained, not mysterious.

## Rules worth knowing

| Rule | Why |
|---|---|
| **An exchange is atomic.** A question and its answer are sent together or not at all, and the pair has the class of the more sensitive of the two. | The answer was written from the question and may quote it. |
| **An answer takes the class of everything the model saw.** | It may quote any of it. So once a confidential message is in a model's context, its later answers are confidential too and stay withheld from less-cleared models. |
| **The new message is never held back.** If it is above the model's clearance the turn is **refused** (HTTP 446), not answered without it. | Answering blind would hide why the answer is wrong. |
| **No silent fallback.** The model is the one you name. There is no experiment variant swap and no retry on another model. A failed call returns an error and stores nothing. | The history was filtered for *this* model. |
| **An unknown class counts as the highest.** | Never guess toward less sensitive. |
| **Routing in `log_only` or `off` sends the whole history**, and records the mode on the context record. Only `enforce` holds anything back. | `log_only` never refuses; `off` is today's behaviour. |

## Who can see what

A conversation belongs to one user and is **private**, **shared with a team** they belong to, or (admins only) **shared with the whole organization**.

| | Owner | Teammate (shared) | Another user | Admin |
|---|---|---|---|---|
| Read messages and what was sent | yes | yes | no (404) | no (404) |
| Add messages, rename, share, delete | yes | no | no | delete only |
| List | `scope=mine` | `scope=shared` | | `scope=org`: titles, owners and sizes only |

An organization-wide conversation is readable by every member of the org (and no other org) and writable by its owner only; only an admin can publish one, and unpublishing it takes access away at once.

An admin can delete any conversation, which is written to the admin audit log with the owner and visibility but never the content. A conversation you may not see is a 404, so its existence is not revealed. Deleting a team makes its conversations private to their owners.

## Standing instructions (personas)

A conversation can carry a **standing instruction** (`system_prompt`, up to 4,000 characters): "You are a terse code reviewer." It is sent with every message and a single message can override it. It is part of what the model receives, so it is classified and routed like the message: a sensitive instruction cannot reach a model that is not cleared for it. It is not stored as a turn.

## Trying routing first

With routing in `log_only`, history is sent whole, but each answer's context record carries `would_withhold`: what enforcement would have held back from that model. Read it in the context drawer to see the effect before you enforce.

## What is stored

- A conversation idle for longer than your plan's audit retention (7 days on free, up to 365 on enterprise) is deleted whole, with its messages and context records. An active conversation is never cut short.
- Messages are stored with personal data replaced (the same detector as [payload capture](/guides/payload-capture)) and capped at 50,000 characters. The model receives what the user typed; only the stored copy is redacted, so later history contains the redacted text.
- Each message keeps its data class and, for answers, the model that wrote it.
- The context record keeps the ids of the messages sent and held back, the class and routing mode, a size estimate and a **SHA-256 of the exact messages sent**. It is append-only: the application can add records but not change or remove them (they go when their conversation is deleted). The hash lets an auditor check a claim about what a provider received without a second copy of the text.

## Streaming

Send `"stream": true` with a message and the answer comes back as server-sent events as it is written:

| Event | Data |
|---|---|
| `context` | First: the model, the class of what was sent, which earlier messages were **held back** (and any `would_withhold` preview). The same guards as a whole answer ran before this. |
| `delta` | `{"text": "…"}`, as many as it takes. |
| `done` | The stored exchange, exactly as the non-streaming response. |
| `error` | The answer broke part-way. **Nothing is stored** (half an answer is not a turn); the attempt is recorded. |

A refusal (446), an unknown model or a policy block is an ordinary error response **before** any stream starts. If the caller disconnects, nothing is stored and the abandoned call is audit-logged (status 499) with what had been delivered. The conversation is locked for as long as the stream runs.

Streaming is **refused** (422 `streaming_unavailable`) for an organization that has response guardrails on: the answer must be checked in full before any of it is delivered, which a stream cannot do. Ask without streaming instead. The console does this automatically.

## Limits

- Replies are returned whole unless you ask for a stream (see above).
- One message at a time per conversation (a second returns 409 `turn_in_progress`).
- A user keeps at most 500 conversations. A message is at most 20,000 characters.
- Not included: long-term memory across conversations, retrieval over documents, personas, org-wide sharing.

See the [API reference](/api-reference/conversations).
