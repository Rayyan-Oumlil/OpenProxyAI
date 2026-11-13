---
slug: when-every-authorized-provider-is-down
title: "When every authorized provider is down, the right answer is an error"
tags: [architecture, engineering]
description: A gateway that fails over to anything turns an outage into a data transfer. What our gateway returns when the only approved route is unavailable, with real output, how to tell a policy refusal from an infrastructure error, and how to build a second approved path before you need it.
---

Availability and authorization pull in opposite directions at the worst moment. A provider has a bad hour. Your gateway has a retry path. If that path can reach any model that is up, then the sensitive prompt you routed carefully an hour ago is now going somewhere nobody approved, and nobody decided that. An outage became a data transfer.

The alternative sounds harsh and is correct: when every route that is allowed to serve this request is unavailable, the request fails, quickly and clearly. This post shows what that looks like in OpenProxyAI, in real output, and what to build so it rarely happens.

{/* truncate */}

## What it looks like

Everything below ran against the demo stack. The model `openai/gpt-6.1-sol` is registered, cleared for internal data, and served by a single provider key. First, with routing enforced and the key healthy:

```text
HTTP 200
  x-openproxyai-model: openai/gpt-6.1-sol
  x-openproxyai-route-reason: authorized
```

Now the only key is switched off, as it would be if you pulled it during an incident. Routing is still enforced:

```text
HTTP 446
  x-openproxyai-policy-action: block
  x-openproxyai-route-model: none
  x-openproxyai-route-reason: not_authorized:key_inactive
```

```json
{
  "error": "routing_blocked",
  "reason_code": "no_authorized_model",
  "explanation": "openai/gpt-6.1-sol is not available to your organization right now.",
  "route_reason": "not_authorized:key_inactive",
  "detail": "No model authorized for this request's data class can serve it."
}
```

Three things to notice. The refusal is immediate, because the gateway worked out up front that nothing was allowed to serve this request and called no one. The reason is specific: `key_inactive`, not a generic failure. And the `explanation` is a plain sentence a person can read, written so it names the model that was asked for and nothing about the rule behind it.

Sending a caller-chosen fallback header does not change the outcome. In the same run, a request that named `openai/gpt-4o-mini` as its backup got the identical 446.

### The same outage with routing off

For contrast, the same key switched off with routing in its default `off` mode:

```text
HTTP 503
{"error": "no_provider_key",
 "detail": "No provider keys available for region 'us'. Add provider keys tagged with region 'us' or 'global'."}
```

Two different statuses, on purpose.

| Status | Means | What your code should do |
|---|---|---|
| 446 | A policy or routing decision. The request is not allowed to go anywhere right now. | Do not retry blindly. Show the `explanation`, or queue the work. |
| 503 and other 5xx | The gateway or a provider could not serve it. | Retry with backoff. |

Keeping them apart is the point. An application that retries a 446 in a loop is trying to talk its way past a control. An application that gives up on a 503 is throwing away a request that would have succeeded a second later.

## What this does not show

Be careful about what the demo proves. It shows a key being unavailable, which is the failure an operator causes or a credential revocation causes. It does not simulate a provider returning 5xx errors mid-request. For that, the rule is the same one, covered in [Your failover can leak your data](/blog/failover-can-leak-data): every retry may only pick from the set of models authorized for the request, and if that set is empty the request is refused. I have not run a live provider outage for this post.

## Build a second approved path before you need it

An error is the right answer when nothing approved is available. The better outcome is that something approved almost always is.

1. **Register a second model and key inside the same clearance.** The new route must be cleared for the same data class, in the same regions, within your risk limit. Two keys for one model in the same account is not a second path. A second provider or a second account is.
2. **Give them one capability name.** If callers ask for `cap:SUMMARIZE` instead of a model name, the registry can serve the request from whichever authorized model is available, with no change in the application. See [Two model retirements](/blog/model-retirements-nov-30-dec-11) for the setup.
3. **Turn on health checks.** `PROVIDER_HEALTH_CHECK_ENABLED` polls provider keys in the background so the router avoids a degraded one, and `ADAPTIVE_LB_ENABLED` shifts weight by observed latency. The console shows the result, key by key.
4. **Decide what degrades.** Some work can wait. The batch API takes a file and works through it in the background, so work that can wait does not need an answer in seconds. Some work can be served from the exact cache for a while. Some work needs a smaller authorized model. Decide that per use case now, not during the incident.
5. **Rehearse it.** In a staging copy, switch off a key and run your traffic. Check three things: that callers see 446, not a hang; that nothing retries in a loop; and that your alert fires.

![The OpenProxyAI provider health page. Counters for healthy, degraded, down, not checked and disabled keys, and a table with one key showing its state, last health check, p99 latency, error rate and weight. In this demo health checks are off, so the key shows as Not checked.](/img/blog/console-provider-health.png)

In the demo, health checks are off, so the page shows the key as "Not checked" and tells you which setting to enable.

## Checklist for any gateway

Whichever gateway you run, ask these before the incident, not during it.

- When no approved route is available, does it refuse, or does it find another route? Run the test; do not trust the documentation.
- Is a refusal distinguishable from an infrastructure error by status code, so your retry logic can tell them apart?
- Does a caller-supplied fallback get checked against the same rules?
- Do you have a second approved route, in the same region and clearance?
- Who gets paged, and how does the refusal show up in the request log?

## Try it

The demo runs with Docker and needs no provider key. Register a model, switch routing to enforce, then deactivate the key and send a request.

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

See [Provider routing](/core-concepts/provider-routing), [Errors and status codes](/api-reference/errors-and-status-codes) and [Environment flags](/getting-started/environment-flags).

## Sources

- OpenProxyAI docs: [Provider routing](/core-concepts/provider-routing), [Errors and status codes](/api-reference/errors-and-status-codes), [Environment flags](/getting-started/environment-flags).
- Earlier on this blog: [Your failover can leak your data](/blog/failover-can-leak-data) and [Refusals should explain themselves](/blog/refusals-should-explain-themselves).

Output is from a run on the demo stack on November 13, 2026, with a fake provider standing in for the real one.
