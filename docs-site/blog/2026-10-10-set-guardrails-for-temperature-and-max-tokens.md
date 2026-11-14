---
slug: set-guardrails-for-temperature-and-max-tokens
image: /img/blog/og/set-guardrails-for-temperature-and-max-tokens.png
title: "Set guardrails for temperature and max tokens, once, for every team"
tags: [product, engineering]
description: "Let apps ask for creativity, reasoning depth and answer length in plain words, and set organization defaults and a ceiling. A runaway temperature or a huge max_tokens stops being a billing surprise."
---

Every model provider has its own knobs for how creative an answer is, how long it can be and how hard the model thinks. Applications set them in a dozen places, and any one of them can quietly drive cost or quality in the wrong direction. A copied snippet with a very high temperature, or an answer length set far above what the feature needs, is easy to miss in review. OpenProxyAI gives you two things: a provider-neutral way to ask for behavior, and an organization-level ceiling that no caller can go above.

{/* truncate */}

![An application asks for a behavior. The gateway applies organization defaults if the caller said nothing, lowers anything above the ceiling, and tells the caller what it did in a response header.](/img/blog/set-guardrails-for-temperature-and-max-tokens.svg)

## One vocabulary, every provider

Providers name the same ideas differently. Behavior settings let an application describe what it wants, and the gateway translates that for whichever model serves the call.

| Setting | Values | What it controls |
|---|---|---|
| `creativity` | low, medium, high | How varied the answer is |
| `reasoning_depth` | low, medium, high | How much the model reasons, on models that support it |
| `max_response_length` | short, medium, long | How long the answer can be |
| `citations` | true or false | Asks the model to name its sources, and to say plainly when it has none |

The application can send these in a header or in the request body. With an OpenAI SDK, that is an extra header or an extra body field, so there is nothing new to install.

```http
x-openproxy-behavior: creativity=low; max_response_length=short
```

Nothing changes until someone sets a value. An organization that never uses behavior settings runs exactly as before, so you can adopt them one team at a time.

## Defaults and a ceiling

Two controls live in the organization policy, under Policy and then Behavior in the console.

- **Defaults** describe what a call is like when the caller says nothing. Set a medium response length as the default and every call that does not ask for something else gets it.
- **Ceiling** is the most a caller may ask for. Set creativity to medium and long answers to long, and nobody can go beyond that.

An explicit choice by the caller beats a default. Nothing beats the ceiling.

### A request above the ceiling is lowered, not refused

This is the part that keeps teams happy. If an application asks for high creativity and your ceiling is medium, the request still succeeds. It is lowered to medium, and the response says so in a header that names what was changed. The caller is never left with a mysterious failure, and the platform team never has to chase a broken feature.

The ceiling also covers the raw settings a developer might pass directly. A caller who sends their own temperature or token limit is held to the same ceiling, so there is no side door around "medium creativity". While a ceiling is active, other provider parameters that could raise a limit are removed from the call and listed in the request log, so a new provider option cannot quietly bypass your rule. With no ceiling set, a caller's own parameters are left alone.

## Safe by design

| Situation | What happens |
|---|---|
| A setting the model does not support, such as reasoning depth on a model without it | That one setting is ignored and recorded. The call still goes through. |
| An unknown setting or value | The request is refused with a clear error before anything is sent to a provider. |
| A different creativity level | Gets its own cache entry, so a cautious answer is never served in place of a creative one. |
| A setting that would change the answer in other ways | That call skips the cache, so an answer made without the setting is not served instead. |

The request log records what was asked for, what was applied, what was lowered and what was ignored. When someone asks why an answer was short, you can see exactly which setting did it.

## A worked scenario

A company has three uses of the same model: a legal-clause summarizer, a marketing idea generator, and a support assistant.

1. The platform team sets a ceiling of medium creativity and long answers. Nobody gets anything more.
2. They set a default of medium answer length, so a feature that says nothing does not produce thousands of words.
3. The summarizer asks for low creativity and short answers. It gets exactly that.
4. The marketing tool asks for high creativity. It is lowered to medium, the response header says so, and the team decides in the open whether that is acceptable or whether it needs an exception.
5. A developer copies an old snippet with a very high temperature into the support assistant. The ceiling lowers it, and the request log shows what happened.

No application needed a code change for the ceiling to take effect, and cost per answer stops depending on who wrote the call.

## What to do now

- [ ] Look at what your applications set today for temperature and answer length.
- [ ] Set organization defaults for response length first. It is the setting with the most direct effect on cost.
- [ ] Set a ceiling that is generous enough that nothing breaks, then tighten it as you learn.
- [ ] Ask teams to use the plain-word settings in new code.
- [ ] Watch the headers and request log for lowered calls. They show which features want more than you allowed.

## Good to know

Caps on answer length help control cost, but a short ceiling can cut off an answer that really needs room. Start generous, and check the lowered-call numbers before you tighten.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

This needs Docker and no provider key. The console is at http://localhost:5173. If it helps you, star the repo, and if a setting is missing for your use case, open an issue.

## Sources

- [Behavior settings](/core-concepts/behavior-settings): the settings, defaults, ceiling, headers and request log fields.
- [Policies and guardrails](/core-concepts/policies-and-guardrails): where the organization policy fits.
- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets): the other cost controls.
- [Why your AI bill is unpredictable](/blog/why-your-ai-bill-is-unpredictable): the cost problem these controls address.
- [One endpoint, every provider](/blog/one-endpoint-every-provider): why a neutral vocabulary helps across providers.

These statements are based on the sources above and on OpenProxyAI's behavior as of 2026-10-10.
