---
slug: when-every-authorized-provider-is-down
title: "When every authorized provider is down, the right answer is a clear error"
tags: [architecture, engineering]
description: A gateway that fails over to anything turns an outage into a data transfer. OpenProxyAI returns a fast, explicit refusal when the only approved route is unavailable, and lets you build a second approved path so it rarely comes to that.
---

Availability and authorization pull in opposite directions at the worst moment. A provider has a bad hour. Your gateway has a retry path. If that path can reach any model that is up, then the sensitive prompt you routed carefully an hour ago is now going somewhere nobody approved, and nobody decided that. An outage became a data transfer.

The alternative sounds harsh and is correct: when every route that is allowed to serve this request is unavailable, the request fails, quickly and clearly. This post shows what that looks like in OpenProxyAI, in real output, and how to build so it rarely happens.

{/* truncate */}

## What it looks like

Everything below ran against the demo stack. The model `openai/gpt-6.1-sol` is registered, cleared for internal data, and served by a single provider key. First, with routing enforced and the key healthy, the request succeeds and the response names the model that served it. Now the only key is switched off, as it would be if you pulled it during an incident:

```text
HTTP 446
```

```json
{
  "error": "routing_blocked",
  "reason_code": "no_authorized_model",
  "explanation": "openai/gpt-6.1-sol is not available to your organization right now."
}
```

Three things to notice. The refusal is immediate, because the gateway worked out up front that nothing was allowed to serve this request and called no one. The reason is specific, so your team knows where to look. And the `explanation` is a plain sentence a person can read, naming the model that was asked for and nothing about the rule behind it.

Sending a caller-chosen fallback does not change the outcome. In the same run, a request that named `openai/gpt-4o-mini` as its backup got the identical 446.

## Telling a refusal from an outage

Two kinds of failure get two different statuses, on purpose.

| Status | Means | What your code should do |
|---|---|---|
| 446 | A policy or routing decision. The request is not allowed to go anywhere right now. | Do not retry blindly. Show the `explanation`, or queue the work. |
| 503 and other 5xx | The gateway or a provider could not serve it. | Retry with backoff. |

Keeping them apart makes client code simple. A 446 is an answer to act on, and a 5xx is a moment to wait and try again, so your retry logic never fights a control.

## Build a second approved path before you need it

An error is the right answer when nothing approved is available. The better outcome is that something approved almost always is.

1. **Register a second model and key inside the same clearance.** The new route is cleared for the same data class, in the same regions, within your risk limit. A second provider or a second account gives you a real second path.
2. **Give them one capability name.** If callers ask for `cap:SUMMARIZE` instead of a model name, the registry can serve the request from whichever authorized model is available, with no change in the application. See [Two model retirements](/blog/model-retirements-nov-30-dec-11) for the setup.
3. **Turn on health checks.** Background checks on provider keys let the router steer away from a degraded one, and the console shows the result key by key. See [Provider routing](/core-concepts/provider-routing).
4. **Decide what degrades.** Some work can wait: the batch API takes a file and works through it in the background. Some work can be served from the exact cache for a while. Some work can use a smaller authorized model. Decide that per use case now, not during the incident.
5. **Rehearse it.** In a staging copy, switch off a key and run your traffic. Check that callers see 446 instead of a hang, that nothing retries in a loop, and that your alert fires.

![The OpenProxyAI provider health page. Counters for healthy, degraded, down, not checked and disabled keys, and a table with one key showing its state, last health check, p99 latency, error rate and weight.](/img/blog/console-provider-health.png)

## Checklist for any gateway

Whichever gateway you run, ask these before the incident, not during it.

- When no approved route is available, does it refuse, or does it find another route? Run the test.
- Is a refusal distinguishable from an infrastructure error by status code, so your retry logic can tell them apart?
- Does a caller-supplied fallback get checked against the same rules?
- Do you have a second approved route, in the same region and clearance?
- Who gets paged, and how does the refusal show up in the request log?

The rule behind all of this is the one in [Your failover can leak your data](/blog/failover-can-leak-data): every retry picks only from the set of models authorized for the request, and an empty set means a refusal.

## Try it

The demo runs with Docker and needs no provider key. Console at http://localhost:5173. Register a model, switch routing to enforce, then deactivate the key and send a request.

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

If it is useful, star the repo or open an issue with the failure drills you want covered.

## Sources

- OpenProxyAI docs: [Provider routing](/core-concepts/provider-routing), [Errors and status codes](/api-reference/errors-and-status-codes).
- Earlier on this blog: [Failover without leaks](/blog/failover-can-leak-data) and [Refusals should explain themselves](/blog/refusals-should-explain-themselves).

These statements are based on OpenProxyAI's behavior at the post date.
