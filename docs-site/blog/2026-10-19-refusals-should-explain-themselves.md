---
slug: refusals-should-explain-themselves
title: "A refusal should say why in one sentence, and never say too much"
tags: [product, security]
description: A gateway that blocks a request owes the person behind it a clear answer, without handing them a map of your controls. Here is how OpenProxyAI refuses well.
---

When a gateway refuses a request, two people are waiting on the answer. The developer wants a machine-readable reason. The person who typed the prompt wants to know what to do next. Most gateways serve only the first one: a status code, a reason string, maybe a rule name.

{/* truncate */}

## Why the rule name is the wrong thing to show

A reason like `blocked_keyword:acme-merger` tells a developer exactly what happened. Shown to an end user, it tells them which word to rewrite. A refusal that names the pattern is a hint for evasion, and one that names the mechanism behind the decision leaks how your controls are built.

So an OpenProxyAI refusal carries two separate things:

- **A stable reason code** for the developer and the audit log: specific, machine-readable, not meant for end users.
- **An explanation** for the end user: one plain sentence.

## What the sentence says

An explanation uses only what the caller already knows: the model they asked for and the kind of data in their own request. For a routing refusal it reads like this: "openai/gpt-4o is not approved for confidential data in your organization." For a policy block it names the category in general words ("This request contains wording that your organization's policy does not allow") and stops there. Whether a model is disabled, has no key, or is simply not cleared for the data, the person sees one calm answer: "not available to your organization right now."

The result is a refusal that is useful to the person who hit it and uninteresting to anyone probing for gaps.

## Where it shows up

- Every policy block, returned as HTTP 446, includes the explanation next to the existing fields.
- The request trace in the console shows what the caller was told, next to the real reason.
- The policy preview shows what a caller would be told before you turn a rule on, so you can read your own refusals the way a user will.
- Both SDKs expose the explanation on the policy error, so an application can show it directly.

## Why 446

Policy blocks use HTTP 446, not 403. A 403 should mean "you are not authorized," which is a different problem with a different fix: a key without a permission is an access-control question, while a prompt that contains a card number is a data question. Keeping them apart makes dashboards, alerts and client retry logic honest.

## Good to know

Applications that serve several languages can map the stable reason code to their own text and use the gateway's sentence as the fallback.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker and no provider key. The console is at http://localhost:5173. Send a request that policy blocks and read the refusal your users would see. If it is useful, star the repo or open an issue with the refusal you would like to see.

These statements are based on OpenProxyAI's behavior at the post date.
