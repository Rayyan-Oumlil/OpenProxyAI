---
slug: run-local-models-through-the-same-gateway
title: "Run local models through the same gateway, with the same policies and budgets"
tags: [product, security]
description: "Ollama, vLLM and other self-hosted endpoints can sit behind the same OpenAI-compatible API as your cloud models, with the same policy checks, budgets and audit trail, and a clearance level for sensitive data."
---

Some prompts should never leave your network. Customer records, health data and internal source code are common examples. Many teams answer that with a model they run themselves, using Ollama or vLLM. Then a second problem appears: the local model lives outside the controls everything else has. No budget, no audit trail, no policy, and applications need separate code to reach it. You can instead put it behind the same gateway as your cloud models. This post shows how, and how to make sure sensitive requests only ever reach it.

{/* truncate */}

![A request containing a social security number is classified confidential by the gateway. The cloud model is cleared only for internal data, so the request goes to the local model, which is cleared for confidential data. If the local model is down the request is refused with HTTP 446 and is never sent to the cloud model.](/img/blog/run-local-models-through-the-same-gateway.svg)

## What is supported

OpenProxyAI can point a provider key at a custom endpoint. Any server that speaks the OpenAI-compatible API works, and the documentation names vLLM and Ollama (through its OpenAI-compatible address) as examples. You register it like any other provider key, then your applications reach it through the same gateway endpoint and the same gateway key they already use.

![The Provider keys page of the admin console, listing each key with its provider, alias, region, endpoint, maximum data class, weight and status.](/img/blog/console-provider-keys.png)

The list in the console has columns for the endpoint and the maximum data class, so you can see at a glance which keys point at your own servers and what they may receive.

## What carries over

A local model behind the gateway goes through the same request pipeline as a cloud model. That means:

| Control | For a local model |
|---|---|
| Policy checks | The same allowlists, keyword rules, PII checks and prompt-injection checks apply. |
| Budgets and rate limits | Requests count toward the same limits for organization, team and user. |
| Audit log | Every call is recorded like any other, with the decision and the model that served it. |
| Streaming | Supported for chat. |
| Failover | The key takes part in routing and failover like any other key. |
| Embeddings | Supported through the same kind of endpoint. |
| Data-class routing | You decide which data classes the local endpoint may receive. |

## Keep sensitive data on your own model

This is the main reason to do it. Every request is classified as public, internal, confidential or secret. The class comes from your organization's default, an optional header from the caller that can only raise it, and what the gateway detects in the text, such as a social security number or a payment card number.

Each provider key carries a clearance: the most sensitive class its endpoint may receive. In the model registry, each model is linked to the key that serves it. With data-class routing enforced, a model only serves a request if it is cleared for that request's class, and it is only served through its own registry key.

A scenario:

1. You register your cloud model with a clearance of internal.
2. You register your local model, on a server in your own network, with a clearance of confidential.
3. A request arrives with a customer's social security number in it. The gateway classifies it as confidential.
4. The cloud model is not cleared for that class, so it is ruled out. The local model serves the request.
5. If the local server is down, the request is refused with HTTP 446 and a plain reason. It is not sent to the cloud model as a fallback.

You can test this before enforcing it. The policy preview shows which model would serve a sample request and why the others were ruled out, without calling any model or using any budget.

## Models without a price

Cloud providers publish per-token prices. A model on your own hardware often has no listed price. The gateway still returns the answer. It charges a flat per-call estimate and marks the call as an estimate in the audit record, so a model nobody can price still counts toward budgets. See [rate limiting and budgets](/core-concepts/rate-limiting-and-budgets). If you want a different number, your operator can change the flat amount.

## Setting it up

1. Start your model server and note its OpenAI-compatible address.
2. Ask your operator to allow private endpoints on the gateway. This is an operator-level setting, off by default, because it lets an administrator aim the gateway at the internal network. It is on in the demo. Leave it off on a gateway shared by unrelated tenants.
3. In the console, add a provider key with the provider set to the OpenAI type, the address of your server, the endpoint marked as internal, and a clearance such as confidential. The key value can be any placeholder your server accepts. Provider keys can also come from your secret store, see [provider keys from Vault](/guides/secrets-from-vault).
4. Add the model to the registry and link it to that key.
5. Use the policy preview to check where sample requests would go.
6. Turn routing from log-only to enforce when the decisions look right.

The gateway checks the endpoint when you save it and again before each call. Redirects are never followed, the connection goes to the address it checked, and addresses for cloud metadata services are always refused. Public endpoints must use https. In an air-gapped deployment, mark the endpoint as internal.

## What to do now

- Decide which data classes must stay on hardware you run.
- Pick a model server and confirm it exposes an OpenAI-compatible address.
- Register it with the lowest clearance that fits, and give your cloud models a lower one.
- Preview a few realistic prompts, including ones with personal data, before enforcing.
- Watch the audit log for the first week to confirm sensitive requests went where you expected.

## Good to know

Classification depends on what the detector can see, so a sensitive value it does not recognize is treated as less sensitive. Callers can raise a request's class with a header, and you can set a higher default for your organization. The gateway must be able to reach your model server over the network, and your server must keep up with your traffic.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

This needs Docker and no provider key. The console is at http://localhost:5173. If it is useful, star the repo, and open an issue if you run a model server we should document.

## Sources

OpenProxyAI documentation, read at the post date:

- [Environment flags](/getting-started/environment-flags) (private provider endpoints, air-gapped mode)
- [Provider keys API](/api-reference/provider-keys) (custom endpoint and clearance)
- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets) (flat estimate for unpriced models)
- [Request pipeline](/core-concepts/request-pipeline)
- [Provider routing](/core-concepts/provider-routing)
- [Policies and guardrails](/core-concepts/policies-and-guardrails)

These statements are based on OpenProxyAI's behavior at the post date.
