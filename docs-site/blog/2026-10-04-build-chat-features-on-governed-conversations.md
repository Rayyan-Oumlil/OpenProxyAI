---
slug: build-chat-features-on-governed-conversations
image: /img/blog/og/build-chat-features-on-governed-conversations.png
title: "Build chat features on conversations the gateway governs for you"
tags: [product, engineering]
description: "Let the gateway keep chat history, share it with a team, stream answers, and decide which earlier messages each model may see, so your app does not have to build any of that safely by itself."
---

Every team that ships a chat feature ends up building the same plumbing: where history lives, who can read it, how to stream answers, and what happens when the user switches models. Then a security review asks the hard question. If message three held something confidential and message four goes to a different model, who checked that the model should see message three? OpenProxyAI can keep the conversation for you and answer that question by design.

{/* truncate */}

![A conversation with a confidential turn, an internal turn, a public turn and a new internal message. The model is cleared for internal data, so it receives the internal turn, the public turn and the new message, and the confidential turn is held back.](/img/blog/build-chat-features-on-governed-conversations.svg)

## The problem with stateless chat

Most gateways are stateless. Your application sends the whole history on every call, and the gateway judges each request on its own. That works until history itself becomes the leak.

Picture a finance assistant. A user pastes a customer's account details into message three, with a model that is approved for confidential data. In message four they switch to a cheaper model that is only approved for internal data and ask something harmless. The new message is fine. The history that rides along with it is not.

If your app owns the history, every product team has to remember this rule. If the gateway owns it, the rule is applied once, in one place, for every chat feature you build.

## What the gateway does for each message

When conversations are on, each new message goes through the same steps:

1. The message is classified by sensitivity. The organization default applies, personal data raises it, and a caller can raise it but never lower it.
2. The gateway looks up what the chosen model is cleared to see.
3. It builds the context from earlier exchanges that model is cleared for, newest first. Anything above its clearance is held back.
4. The whole package, system prompt included, is checked by the same policy and routing rules as any other request.
5. The model is called through the normal path, so keys, metering and the audit log all apply.
6. On success the exchange is stored, and a context record notes which earlier messages were sent and which were held back.

The response tells you what was held back. An answer that seems to have lost context is explained, not mysterious. If a new message is itself above the model's clearance, the turn is refused with the same 446 status as a policy block, instead of being answered with half the picture.

Two details make this safe in practice:

- A question and its answer travel together or not at all, because the answer may quote the question.
- An answer takes the sensitivity of everything the model saw, so a confidential exchange stays out of less-cleared models later.

## Who can see a conversation

Chat features need sharing, and sharing is where privacy goes wrong. Conversations here have three levels.

| Visibility | Who reads it | Who can add messages |
|---|---|---|
| Private (default) | The owner | The owner |
| Shared with a team | Members of that team | The owner |
| Organization-wide | Every member of the organization | The owner |

Only an admin can publish a conversation organization-wide, and unpublishing takes access away at once. A conversation you may not see looks like it does not exist, so nobody can probe for titles. Admins can delete a conversation if they must, and the deletion is written to the admin audit log with the owner and visibility, never the content. The org-wide listing shows titles, owners and sizes only.

There is also a **keep private** switch. Turn it on and the conversation can never be shared until you turn it off. Adding it to a conversation that is already shared stops the sharing.

## Features your users will ask for

Once history lives in the gateway, a lot of product work disappears.

- **Tags and spaces.** Label conversations (finance, q3) and group them into spaces, which work like project folders. A space can belong to a team, but it is a way to find things, not a way to share them. A teammate sees a conversation in a team space only if it was already shared with them.
- **Search.** It looks at titles and tags only, never at what was said, so a search can never reveal content.
- **Standing instructions.** A conversation can carry a persona, such as "You are a terse code reviewer." It goes with every message, and a single message can override it. It is classified and routed like any other text, so a sensitive instruction cannot reach a model that is not cleared for it.
- **Switching models mid-way.** Users can change models between messages. The gateway re-applies the clearance rules each time, which is the safe version of a feature people love.- **Streaming.** Ask for a stream and answers arrive as they are written. The first event describes what was sent and what was held back, then the text arrives in pieces, then a final event carries the stored exchange. If the answer breaks part-way, nothing is stored and the attempt is still recorded.

The console has a Conversations page, so admins and users can browse, filter by tag, and open a "what was sent" drawer for any answer.

## Stored data you can defend

Conversations are the first feature that stores what users said on purpose, so they are off by default. When you turn them on:

- Messages are stored with personal data replaced. The model still receives exactly what the user typed, but the stored copy, and so later history, contains the redacted text.
- Each message keeps its sensitivity class, and each answer keeps the model that wrote it.
- Each context record keeps the ids of what was sent and held back, plus a fingerprint of the exact messages sent. An auditor can check a claim about what a provider received without a second copy of the text. These records are append-only.
- An idle conversation is deleted whole once your plan's retention period passes. An active one is never cut short.
- The gateway never reuses one person's conversation as context for someone else.

## Try it in log-only first

If you are not sure what enforcement would change, route in preview mode first. History is sent whole, but every answer's context record shows what enforcement would have held back from that model. Read it in the context drawer, then enforce when the picture is clear.

## What to do now

- Decide which chat features should live in the gateway, and which sensitivity classes your models are cleared for.
- Turn conversations on from the Policy screen, under Evaluation, in a test organization.
- Create a private conversation, share one with a team, and check what a teammate and an admin each see.
- Switch models mid-way with routing in preview mode, and read the context record.
- Move routing to enforce once the preview matches your expectations.

## Good to know

Streaming asks the gateway to deliver text as it is written. Organizations that turn on response guardrails must check each answer in full before any of it goes out, so those organizations ask for whole answers instead. The console handles this automatically.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

It needs Docker and no provider key. The console is at http://localhost:5173. If it is useful, star the repo or open an issue with the chat feature you want to build next.

## Sources

- [Conversations guide](/guides/conversations): visibility, retention, streaming and the full rules.
- [Policies and guardrails](/core-concepts/policies-and-guardrails): the checks every package goes through.
- [Provider routing](/core-concepts/provider-routing): how model and key choice work.
- [Audit logging](/security/audit-logging): what is recorded for each call.
- [Shadow AI needs a governed front door](/blog/shadow-ai-needs-a-governed-front-door): why one governed entry point matters.

These statements are based on the OpenProxyAI documentation and the product's behavior at the post date.
