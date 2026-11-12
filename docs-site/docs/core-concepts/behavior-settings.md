---
title: Behavior Settings
description: Ask for creativity, reasoning depth, answer length and citations without knowing each provider's parameters, and let your organization set defaults and a ceiling.
---

# Behavior Settings

Every provider names the same ideas differently: `temperature`, `top_p`, `reasoning_effort`, `max_tokens`, `max_completion_tokens`. **Behavior settings** let an application say what it wants in provider-neutral words, and let your organization decide how far that can go.

| Setting | Values | What the model receives |
|---|---|---|
| `creativity` | `low`, `medium`, `high` | `temperature` 0.2, 0.7 or 1.0 |
| `reasoning_depth` | `low`, `medium`, `high` | `reasoning_effort`, only for models that accept it |
| `max_response_length` | `short`, `medium`, `long` | `max_tokens` 256, 1,024 or 4,096 |
| `citations` | `true`, `false` | A short instruction to name sources and to say when there is none |

A setting changes nothing unless someone sets it. An organization that never uses them runs exactly as before.

## Asking for behavior

With a header (works with any OpenAI SDK through `extra_headers`):

```http
x-openproxy-behavior: creativity=low; max_response_length=short; citations=true
```

Or with a `behavior` field in the body (`extra_body` in the OpenAI SDK):

```json
{ "model": "openai/gpt-4o", "messages": [{"role": "user", "content": "Summarize this."}],
  "behavior": { "creativity": "low", "max_response_length": "short" } }
```

If both are given, the body wins for the settings it names. The `behavior` field is never forwarded to the provider. An unknown setting or value is a `400` with error `invalid_behavior`; nothing is sent.

Conversation turns take the same object in the body of `POST /api/v1/conversations/{id}/turns`, and the playground compare endpoint takes it as `behavior`.

## What your organization controls

On the policy (**Policy > Behavior** in the console, or `PATCH /api/v1/organizations/current/policy`):

- **`behavior_defaults`**: what a call is like when the caller says nothing. Citations may be a default.
- **`behavior_ceiling`**: the most a caller may ask for. There is no ceiling for citations.

```json
{ "behavior_defaults": { "max_response_length": "medium" },
  "behavior_ceiling": { "creativity": "medium", "max_response_length": "long" } }
```

Send the whole object each time (`{}` clears it; `null` is refused so a clear cannot happen by accident).

### The ceiling only ever lowers

- A request above the ceiling is **lowered to it**, not refused. The response says so:

  ```http
  X-OpenProxyAI-Behavior: creativity=medium
  X-OpenProxyAI-Behavior-Clamped: creativity
  ```

- A ceiling also lowers the caller's **own** `temperature`, `max_tokens` and `reasoning_effort`. Otherwise `temperature=2` would walk around a "medium creativity" ceiling. With **no** ceiling set, a caller's raw parameters are never touched.
- A raw parameter the caller sends always beats a **default** (it was an explicit choice) but never beats the ceiling.

## What the provider actually receives

Only parameters the model supports are sent. If you ask for `reasoning_depth=high` on a model that has no reasoning effort, that one setting is **ignored and recorded**; the call still goes through. Nothing is sent that the provider would reject, and if the model's supported parameters cannot be determined, nothing derived from behavior settings is sent.

The request log (and the trace in the console) shows, under `behavior`:

```json
{ "requested": {"creativity": "high"}, "effective": {"creativity": "medium"}, "clamped": ["creativity"],
  "applied": {"temperature": 0.7},
  "ignored": [{"param": "reasoning_effort", "reason": "the model does not accept it"}],
  "clamped_params": [] }
```

## Caching

The answer cache is keyed on the model, the messages and the temperature. `creativity` changes the temperature, so different creativity levels never share a cached answer. A setting that changes anything else (`reasoning_depth`, `max_response_length`) makes that call skip the cache, because an answer made without it would otherwise be served in its place. `citations` changes the messages, so it has its own cache entries.

## Citations

`citations` adds a fixed instruction after the leading system messages: name a specific source, document or earlier message you rely on, and say plainly when you have none. It asks the model to be honest about sources; it cannot make a model that has no sources produce real ones. In a conversation the instruction joins the system prompt before the context is built, so the context record's hash covers it.
