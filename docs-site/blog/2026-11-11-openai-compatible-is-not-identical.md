---
slug: openai-compatible-is-not-identical
title: "OpenAI-compatible is not the same as identical: what a gateway smooths over"
tags: [engineering, product]
description: "Many providers speak an OpenAI-style API, and the details still differ: tool calls, streaming, usage numbers, errors and parameters. Here is what a gateway can smooth over, and what to test yourself."
---

"OpenAI-compatible" is a useful promise. It means you can point an existing SDK at a new base URL and get a response. It is not a promise that every field, every stream chunk and every error matches. Teams find the gaps late, usually in production: a usage number that is missing on a stream, an error that arrives in a different shape, a parameter one model rejects. This post lists where the seams are, what OpenProxyAI does about each, and what you should still test.

{/* truncate */}

![Your app on the left sends one request shape to a gateway in the middle. The gateway smooths provider and model names, tool calls, streaming chunks, usage and cost on streams, behavior settings and error origin headers. On the right, it reaches provider A and provider B, with a dashed amber box noting that details differ per provider.](/img/blog/openai-compatible-is-not-identical.svg)

## Why "compatible" leaves gaps

A chat completion has many moving parts. The core is stable: messages in, a message out. The edges are where providers diverge, because each has its own features, limits and naming. Routers and gateways exist partly to hide this. OpenRouter, for example, documents that it "normalizes the schema across models and providers" ([OpenRouter API overview](https://openrouter.ai/docs/api-reference/overview)). The goal is the same wherever you run it: your application should not carry a pile of per-provider special cases.

Below are the five seams that cause the most surprises, and how OpenProxyAI handles each.

## 1. Model names and routing

Providers name models differently, and some names exist at more than one provider. OpenProxyAI addresses models as provider and model together, such as `openai/gpt-4o`. A name without a provider is rejected with a clear 400 error instead of guessed ([chat completions](/api-reference/chat-completions)).

Each response tells you what actually served the request, in the provider and model response headers, plus the cost of the call ([API reference overview](/api-reference/overview)). If failover moved the request to another key or to a backup model you allowed, you can see it.

## 2. Tool calls

Function calling is where "compatible" differs most. Apps send a list of tools, the model replies with calls, the app returns results, and the loop continues.

What the gateway does here:

- The request and response keep the OpenAI-shaped fields. Fields beyond the basics, such as tools and the response format, are passed through to the provider ([OpenAI SDK and frameworks](/integrations/openai-sdk-and-frameworks)).
- Policy sees the tool traffic. Tool calls to MCP servers can be checked against allow and block lists, and every call is logged ([MCP gateway](/guides/mcp-gateway)).
- Requests that use tools, carry tool results, or ask for a structured response format skip the answer cache, so one request never receives another's stored answer.

Worth testing: how each model behaves with many tools or deeply nested arguments. A gateway can carry the shape. It cannot make two models equally good at choosing tools.

## 3. Streaming

Streaming sends the answer as server-sent events in small chunks. The OpenProxyAI gateway returns standard chunk objects in the OpenAI streaming format, so the same SDK code works for every provider ([chat completions](/api-reference/chat-completions)).

Two practical details are handled for you:

- **The stream is opened before anything reaches you.** The gateway reads the first chunk first, so a temporary provider failure while opening the stream can fail over to another key (or to a backup model you allow). Once content has started to flow, switching mid-answer is not possible.
- **Budget checks happen before the stream starts.** A streamed request is estimated up front; if it would exceed the remaining daily budget, it is refused with HTTP 402 rather than cut off halfway ([rate limiting and budgets](/core-concepts/rate-limiting-and-budgets)).

For more on the mechanics of proxying a stream, see [streaming through a proxy](/blog/streaming-sse-proxy-design) and [real streaming in the Python SDK](/blog/python-sdk-real-streaming).

## 4. Usage and cost

Token counts drive your bill, and streams are where they go missing. Providers often report usage on a stream only when asked, and the extra chunk that carries it can surprise a client that did not expect it.

OpenProxyAI handles both sides:

- It asks the provider for usage on streamed calls, so cost can be recorded.
- If your client did not ask for usage, the extra usage chunk is removed before the stream reaches you. If it did, you get it.
- If a provider reports no usage at all, the gateway estimates it from the prompt and the streamed output, including text in tool-call arguments and reasoning content, so the call is still priced and counted against budgets. A model with no known price is charged a flat placeholder fee and marked as an estimate ([other endpoints](/api-reference/other-endpoints)).
- Streams that end early, for example when a client disconnects, are still recorded once.

The result is that cost per request, and per team, is comparable across providers instead of depending on which fields each one returned ([know who spends what on AI](/blog/know-who-spends-what-on-ai)).

## 5. Errors

Errors differ in status codes, body shape and wording. The gateway gives you two things to rely on:

- **A stable set of gateway statuses.** 401 for a bad key, 429 for a rate or budget limit with a field naming which limit, 402 for a streamed request over budget, and 446 for a policy or routing block, with a plain-language explanation field ([errors and status codes](/api-reference/errors-and-status-codes)).
- **A clear origin.** Every proxied response carries a header saying whether the gateway itself produced the error or refusal, so you can tell "we blocked this" from "the provider failed". The SDKs map the same split to different exception types ([Python SDK](/integrations/python-sdk)).

Upstream error text is not passed through verbatim in production, to avoid leaking provider internals; the detail is kept for operators.

## Parameters: say what you want, not how each provider spells it

Temperature, top-p, maximum tokens, reasoning effort: the names and ranges vary, and some models reject parameters they do not support. OpenProxyAI offers provider-neutral behavior settings for creativity, reasoning depth, response length and citations. It sends only the parameters the model supports and records anything it ignored, so a setting that does not apply to a model does not break the call ([behavior settings](/core-concepts/behavior-settings)).

## What to do now

| Step | Why |
|---|---|
| Write a short contract test: one tool call, one stream, one error, per model you use | Catches provider differences before users do |
| Always read cost and provider from the response headers | Same fields for every model |
| Handle 429, 402 and 446 distinctly | They mean different things and need different retries |
| Check the gateway-origin header before alerting on an error | Separates policy blocks from outages |
| Re-run the contract test when you change models | See [test a model change before you ship it](/blog/test-a-model-change-before-you-ship-it) |

## Good to know

A gateway reduces the number of special cases in your code. It does not make every model behave the same. Features that exist only at one provider, and differences in model quality, still need a test on the models you pick.

## Try it

The demo runs with Docker and needs no provider key. Console at http://localhost:5173.

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

If it is useful, star the repo or open an issue with the provider quirk that bit you.

## Sources

- [OpenRouter API overview](https://openrouter.ai/docs/api-reference/overview): states that it normalizes the schema across models and providers.
- OpenProxyAI docs: [chat completions](/api-reference/chat-completions), [errors and status codes](/api-reference/errors-and-status-codes), [behavior settings](/core-concepts/behavior-settings), [OpenAI SDK and frameworks](/integrations/openai-sdk-and-frameworks), [API reference overview](/api-reference/overview).

Vendor statements are from the page above as read on the post date. Statements about OpenProxyAI are based on its behavior at the post date.
