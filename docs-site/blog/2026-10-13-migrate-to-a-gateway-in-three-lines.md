---
slug: migrate-to-a-gateway-in-three-lines
image: /img/blog/og/migrate-to-a-gateway-in-three-lines.png
title: "Migrate to an AI gateway in three lines: keep your OpenAI SDK"
tags: [product, engineering]
description: "OpenProxyAI speaks the OpenAI API. Change the base URL, the key and optionally the model name, and your app gains policy, budgets, caching, failover and an audit log. Here is what stays the same."
---

The biggest objection to adding a gateway is the migration. Nobody wants to rewrite working code, retest streaming and retrain a team on a new client library. OpenProxyAI avoids all of that by speaking the OpenAI API. If your application uses the official OpenAI SDK today, moving it behind the gateway is a change to the client constructor. Your calls, your response handling and your streaming code stay as they are.

{/* truncate */}

![Before and after: the app talks to a provider directly, then to the gateway, which adds policy, budgets, cache, failover and logging in front of many providers](/img/blog/migrate-to-a-gateway-in-three-lines.svg)

## The three lines

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://gateway.your-company.com/v1",   # line 1: your gateway
    api_key=os.environ["OPENPROXY_KEY"],              # line 2: a gateway key
)

response = client.chat.completions.create(
    model="gpt-4o",                                   # line 3: optional, any provider's model
    messages=[{"role": "user", "content": "hi"}],
)
```

The base URL points at your gateway. The key is one issued by the gateway, not by the provider. The model name is only a change if you want to call a model from another provider, because the same request shape works for any provider behind the gateway. The TypeScript package works the same way with its base URL option.

## What stays the same

- **Your SDK and your code.** No new dependency is required. The dedicated Python and TypeScript SDKs exist if you want typed cost and latency data on each response, but you do not need them to migrate.
- **Request and response shapes.** Chat completions, embeddings and the model list use the OpenAI format. Fields the OpenAI API accepts are passed through.
- **Streaming.** Server-sent events arrive as the same chunk objects your code already parses.
- **Other tools.** Frameworks that accept a custom base URL, such as LangChain's OpenAI integration, work the same way. Extra endpoints for reranking, images, speech, transcription and the Responses API sit behind the same key.

## What you gain on day one

Once traffic flows through the gateway, controls that used to live in every application live in one place.

| You get | In plain words |
|---|---|
| Policy engine | Model allowlists, blocked keywords, personal data detection and prompt-injection checks, applied to every call |
| Budgets and rate limits | Per organization, team and user, checked before the provider is called |
| Caching | Exact and semantic caching to cut repeat spend |
| Failover | If a provider key is rate-limited or failing, traffic shifts to a healthy one without client retry code |
| Audit log | Every request, response, policy decision, route and cost, written once |
| Response headers | Each response reports the provider and model used, cost, latency and cache status |

Because the gateway can route to many providers behind one endpoint, you can also swap or add a model without touching application code.

## The small things that do change

Honesty saves migration afternoons, so here is the short list.

- **A new kind of refusal.** If a policy blocks a request, the gateway returns status 446 with a reason code and a one-sentence explanation you can show a person. Budget and rate limits return 429, and a streamed request that would not fit the remaining daily budget returns 402. Add one handler for these, and your app behaves well when governance says no.
- **Keys come from the gateway.** Create one key per service, optionally tied to a team, so spend is attributed from the first request.
- **Optional headers.** A team header, labels and a data class header are available when you want them. None are required.

## A migration plan that fits in a week

1. **Stand it up.** Run the gateway in your environment and register your organization. Add your provider keys once, in the gateway, instead of in every service.
2. **Mirror, do not enforce.** Apply your policy in log-only mode first so you can see what it would block without blocking anything.
3. **Move one service.** Pick a low-risk one. Create its key, change the three lines, deploy.
4. **Check.** Compare the response headers and the request log with what you expect: model, cost, latency, cache status.
5. **Move the rest, one at a time.** Each service is an independent change, and going back is the same three lines in reverse.
6. **Turn on enforcement** when the log looks right.

## What to do now

- List services that call providers directly and how each gets its key.
- Create a gateway key per service, tied to its team.
- Decide your starting policy and run it in log-only mode.
- Add handlers for 446, 429 and 402 to your shared client wrapper.
- Move one service this week.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker and no provider key. The console is at http://localhost:5173. Star the repo or open an issue if a client library you use does not work as described.

## Sources

- Product docs: [Quickstart](/getting-started/quickstart), [Authentication](/getting-started/authentication), [Provider routing](/core-concepts/provider-routing), [Caching](/core-concepts/caching), [Policies and guardrails](/core-concepts/policies-and-guardrails), [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets), [Errors and status codes](/api-reference/errors-and-status-codes).

These statements are based on OpenProxyAI's behavior at the post date.
