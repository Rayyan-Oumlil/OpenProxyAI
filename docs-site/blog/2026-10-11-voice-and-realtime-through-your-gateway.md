---
slug: voice-and-realtime-through-your-gateway
image: /img/blog/og/voice-and-realtime-through-your-gateway.png
title: "Voice and realtime AI through your gateway, with policy, limits and billing"
tags: [product, security]
description: "Live voice sessions are long, hard to inspect and easy to leave ungoverned. See how OpenProxyAI relays OpenAI Realtime sessions while still applying your policy, limits, cost tracking and key revocation."
---

Voice assistants and live copilots are moving from demos to products. They are also the easiest AI traffic to leave outside your controls. A realtime session is one long connection, the audio cannot be read like text, and the provider key often ends up in a browser. OpenProxyAI can sit in the middle of that connection, so a live session follows the same rules as every other request your company sends to a model.

{/* truncate */}

![A voice app connects to OpenProxyAI, which applies policy to text events, checks limits before each response, logs the cost of each response and re-checks the key while the session is live, then relays to an OpenAI realtime session.](/img/blog/voice-and-realtime-through-your-gateway.svg)

## Why realtime is a governance gap

A normal chat call is one request and one response. You can check it, price it and log it in one place. A realtime session is different.

- **It stays open.** A key that is revoked at 10:00 should not keep talking at 10:30.
- **It is cheap to start and costly to run.** Audio is priced differently from text, and usage arrives in pieces as the conversation goes on.
- **Audio is opaque.** You cannot match a keyword list against a voice stream.
- **Browsers need credentials.** A web page cannot add custom headers to a WebSocket, so teams are tempted to ship a provider key to the client.

Each of these has a straightforward answer when a gateway owns the connection.

## How it works

You speak the provider's own Realtime protocol. Your application connects to the gateway's realtime address with the model name, and the gateway opens the matching session at the provider. From the app's side it is the same protocol, with a different address and a gateway key.

Authentication uses your OpenProxyAI key, not the provider's. A server or SDK sends it as a normal bearer header. A browser, which cannot set headers, passes it through the standard WebSocket subprotocol list. The key is never accepted in the URL, because URLs end up in logs. A wrong or missing key is refused before the connection opens.

The provider session itself is opened with your organization's own provider key, which stays on the gateway. That means the key in your app is one you can revoke, scope and rotate, and the provider key never reaches a device. If a gateway key leaks, it is a nuisance rather than an incident, a theme covered in [a leaked key should be a nuisance](/blog/a-leaked-key-should-be-a-nuisance).

## What the gateway applies to a live session

| Concern | What happens |
|---|---|
| Text you send | Instructions, message content and tool outputs go through your organization's policy. A refused event is not forwarded. The app gets an error event, and the session carries on. |
| Audio | Audio cannot be read, so the session is treated as uninspected input and classified as confidential unless your data-class map says otherwise. |
| Unknown events | Events outside the Realtime protocol are answered with an error and not forwarded. |
| Limits | Before each response starts, the gateway checks your rate and budget limits. If one is reached, no response starts and the app gets a clear error. |
| Cost | Each finished response is priced from the usage the provider reports, with audio and text at their own rates, and written to the request log as its own row. |
| Key and policy | The gateway re-checks the key, the user and the policy while the session is open. A revoked key ends the session within a short window. A tightened policy applies to the next message after the policy cache refreshes. |
| Session cap | Sessions have a maximum length and a per-organization concurrency cap, so a loop cannot open them forever. |

The practical result is that realtime is not a side door. A policy block, a budget limit and a revoked key all mean the same thing on a voice session as on a chat request, so your security and finance leads do not need a second set of rules.

## A worked scenario

Imagine a support team that adds a voice helper to its web app. Without a gateway, the page holds a provider key, nobody can see how many minutes of audio are being used, and a policy for keywords or personal data does not apply to the spoken input.

With the gateway in the middle:

1. The web page connects with a gateway key issued for that app and attributed to the support team.
2. The helper's instructions and any typed messages pass policy before they leave.
3. Each response is priced and logged, so the team's spend shows in the same dashboard as its chat traffic. See [know who spends what on AI](/blog/know-who-spends-what-on-ai).
4. When the app is retired, an admin revokes the key and live sessions end within a short window.

## What to do now

- List where voice or live sessions already exist in your company, including prototypes and browser demos.
- Issue gateway keys for them, attributed to a team, so usage and cost appear in the right place.
- Move provider keys out of browsers and onto the gateway.
- Decide the data class for audio input. The default treats it as confidential, which is the cautious choice.
- Set team limits so one runaway session cannot spend a month of budget. See [rate limiting LLM traffic](/blog/rate-limiting-llm-traffic).
- Review your policy for text events, since that is the part of a session the gateway can read.

## Good to know

Realtime support is for OpenAI sessions. Models are named as the provider and model together, and keys that point at a custom endpoint are not used for realtime. Organizations that enforce response guardrails cannot use realtime, because spoken answers stream out as they are produced and cannot be held back for checking. The gateway refuses the session with a clear reason rather than skip the guardrail quietly.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

It needs Docker and no provider key. The console is at http://localhost:5173. If you build voice products, star the repo or open an issue and tell us what your sessions need.

## Sources

- [Environment flags](/getting-started/environment-flags): the realtime switch and its session settings are listed with the other deployment settings.
- [Policies and guardrails](/core-concepts/policies-and-guardrails): what the text checks cover.
- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets): the limits applied before each response.
- [Authentication](/getting-started/authentication): gateway keys and their lifecycle.
- [Streaming proxy design](/blog/streaming-sse-proxy-design): why live streams need care in a gateway.

These statements are based on the OpenProxyAI documentation and the product's behavior at the post date.
