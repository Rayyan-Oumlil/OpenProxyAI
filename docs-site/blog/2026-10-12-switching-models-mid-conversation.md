---
slug: switching-models-mid-conversation
title: "Switching models mid-conversation without leaking the history you already sent"
tags: [security, architecture]
description: A conversation is data too. If a confidential turn could follow a user to a model that is only cleared for internal data, the history would bypass your routing rules. Here is the rule OpenProxyAI uses so it never does.
---

Most data-classification rules look at the message being sent. A conversation is more than that message: every later request re-sends the earlier turns. If someone discusses a customer's health record with a model cleared for it, then switches to a cheaper model cleared only for internal data, the new request carries the whole history with it. A router that only checks the last message would say yes.

{/* truncate */}

## The rule

Before each message the gateway decides which earlier turns the chosen model is cleared to see, and withholds the rest. Then it classifies the **whole package**, system prompt included, and sends it through the same routing check as any other request. Two layers, so each one backs up the other.

## Decisions that follow from it

- **The model is the one the caller names.** There is no fallback and no experiment variant swap inside a conversation. The history was filtered for this model, so the answer comes from that model.
- **An answer takes the class of everything the model saw.** If the model read a confidential turn, its answer is confidential, even if the reply itself looks harmless.
- **An exchange is atomic.** A question and its answer are classed by the more sensitive half, and are withheld or kept together. An unknown stored class counts as the highest.
- **Admins see metadata, not messages.** Reading another user's turns returns a 404, even for an admin. The audit trail shows who, when, which model and which class.
- **The context record is append-only.** For each turn the gateway stores a hash of what was actually sent, so "what did the model see?" has an answer that cannot be edited later.
- **It is opt-in per organization.** Conversations are the first feature that stores what users said by design, so the organization chooses it.

## Good to know

When a model is not shown earlier turns, it may ask the user to repeat something. The console says when turns were withheld, so the behavior is always visible. Tags and spaces help you organize conversations, and a space never widens who can read one. The `private` tag makes a conversation unshareable.

## Try it

The demo runs with Docker and needs no provider key. Console at http://localhost:5173.

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

If it is useful, star the repo or open an issue. See the [Conversations guide](/guides/conversations) for setup.

These statements are based on OpenProxyAI's behavior at the post date.
