---
slug: switching-models-mid-conversation
title: "Switching models mid-conversation can leak the history you already sent"
tags: [security, architecture]
description: A conversation is data too. If a confidential turn can reach a model that is only cleared for internal data after a switch, your routing rules were bypassed by the history. Here is the rule we use.
---

Most data-classification rules look at the message being sent. A conversation is more than that message: every later request re-sends the earlier turns. If someone discusses a customer's health record with a model cleared for it, then switches to a cheaper model cleared only for internal data, the new request carries the whole history with it. Routing checked the last message and said yes.

{/* truncate */}

## The rule

Before each message the gateway decides which earlier turns the chosen model is cleared to see, and withholds the rest. Then it classifies the **whole package**, system prompt included, and sends it through the same routing check as any other request. Two layers, because the first can be wrong about what it withheld and the second does not trust it.

## Decisions that follow from it

- **The model is the one the caller names.** There is no fallback and no experiment variant swap inside a conversation. The history was filtered for this model, so quietly answering with a different one would invalidate the filter.
- **An answer takes the class of everything the model saw.** If the model read a confidential turn, its answer is confidential, even if the reply itself looks harmless.
- **An exchange is atomic.** A question and its answer are classed by the more sensitive half, and are withheld or kept together. An unknown stored class counts as the highest.
- **Admins see metadata, not messages.** Reading another user's turns is a 404, even for an admin. The audit trail shows who, when, which model and which class.
- **The context record is append-only.** For each turn the gateway stores a SHA-256 of what was actually sent, so "what did the model see?" has an answer that cannot be edited later.
- **It is opt-in per organization.** Conversations are the first feature that stores what users said by design, so the organization chooses it.

## What it does not do

- It trusts the classifier. If a sensitive value is missed in turn two, turn five goes out as if it were not there.
- Withholding history changes the answer quality. A model that is not shown the earlier turns may ask the user to repeat themselves. The console says when turns were withheld, rather than hiding it.
- Tags and spaces are organization tools, not permissions: a space never widens who can read a conversation, and the `private` tag makes one unshareable.
