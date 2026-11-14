---
slug: open-source-apache-2-for-a-gateway
title: "Why OpenProxyAI is Apache-2.0, and what that gives you"
tags: [product, architecture]
description: "A gateway sees every prompt and holds your provider credentials. Here is what an Apache-2.0 license gives you, what self-hosting puts under your control, and how to contribute."
---

You would not run a service that reads every prompt your company sends to a model without being able to look at it. A gateway is exactly that service. It sees the text, it brokers the credentials, and it decides what is allowed. We release OpenProxyAI under the Apache License 2.0 so that you can read it, run it yourself and change it. This post explains what the license gives you in plain words, what self-hosting puts under your control, and how to take part.

{/* truncate */}

![Two panels summarizing the Apache-2.0 license. You may: use it commercially, read and change the code, run it on your own servers, redistribute it, rely on a patent license. You must: keep the license and notices and mark files you changed. The license grants no trademark rights and comes with no warranty.](/img/blog/open-source-apache-2-for-a-gateway.svg)

## Why the license matters for a gateway

Infrastructure outlives the decisions that chose it. A gateway you adopt this year will sit in your request path for a long time. Four questions decide how comfortable that is.

1. Can your security team read the code that handles your prompts?
2. Can you run it without asking anyone?
3. Can you fix or extend it if you need something we have not built?
4. What happens to your deployment if the vendor changes direction?

A permissive open-source license answers all four in your favor.

## What Apache-2.0 gives you

This is a summary of the license text, not legal advice. Read the full text before you rely on it.

| Apache-2.0 says | What it means for you |
|---|---|
| Free to use, including commercially | No per-seat or per-request license fee for the code. You can use it in a paid product or inside your company. |
| Read and modify the source | Your reviewers can audit it. Your engineers can patch it. |
| Redistribute, modified or not | You can ship it inside your own platform, or keep an internal fork. |
| A patent license from contributors | Contributors grant you a license to patents covering their contributions. |

It asks for little in return. You keep the license text and notices with the code, and you mark files you changed. The license does not give you the right to use our name or logo as your own, and the software is provided without a warranty. That last point is standard for open source, and it is why you test before you rely on it.

## What self-hosting puts under your control

The license lets you run the gateway. Our design makes running it yours in practice.

- **Your network.** The gateway runs in your environment. Prompts flow from your applications to the gateway to your chosen model provider, with no OpenProxyAI-operated service in the path.
- **Your data.** Request metadata, audit logs and configuration live in your own Postgres database, with row-level security separating organizations. By default only metadata is kept. Saving redacted prompt and answer samples is opt-in.
- **Your credentials.** Provider keys can be stored encrypted by the gateway, or read at request time from your HashiCorp Vault or AWS Secrets Manager. See [provider keys from Vault](/guides/secrets-from-vault).
- **Your identity provider.** Sign-in works through [SSO](/guides/configuring-sso), and user lifecycle through [SCIM](/guides/configuring-scim).
- **Your timeline.** You decide when to upgrade. Each release is documented before you adopt it.
- **Your boundary.** In air-gapped deployments, a single setting turns off calls to third-party services the gateway does not strictly need.

You also get a published description of how we handle security in the [trust center](/security/trust-center).

## What you can build on top

Because the source is open, the things a gateway cannot know about your company can be added by you. You can write policy plugins for rules specific to your business, point the gateway at your own model servers, and send logs and metrics to the systems you already run. If a provider you rely on needs better handling, you are not waiting on a roadmap.

## How to contribute

We would like this to be shaped by the people who run it.

- **Open an issue.** Tell us what blocked you in an evaluation, what a refusal message should have said, or which provider needs better coverage. Concrete reports from real setups are the most valuable thing you can send.
- **Send a pull request.** Fixes, documentation corrections and tests are welcome.
- **Star the repo.** It helps other platform teams find it.

Repository: https://github.com/Rayyan-Oumlil/OpenProxyAI

## What to do now

- Read the LICENSE file in the repo and have your legal team confirm it fits your policy.
- Run the demo and look at what the gateway records for a request.
- List what you would want to change in a gateway you do not control, and check whether you would be allowed to.
- If you ship software to customers, check how the notice and change-marking terms apply to you.

## Good to know

Open source does not mean unsupported by design, but it does mean you operate what you run. Plan for upgrades, backups and monitoring as you would for any internal service.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

This needs Docker and no provider key. The console is at http://localhost:5173. If you find it useful, star the repo, and if something is missing, open an issue.

## Sources

- Apache License, Version 2.0 (patent license in section 3, redistribution conditions in section 4, trademarks in section 6, warranty disclaimer in section 7): https://www.apache.org/licenses/LICENSE-2.0.txt
- OpenProxyAI repository license file: https://github.com/Rayyan-Oumlil/OpenProxyAI
- OpenProxyAI docs: [trust center](/security/trust-center), [row-level security](/security/row-level-security), [environment flags](/getting-started/environment-flags)

These statements are based on the sources above and on OpenProxyAI's behavior at the post date.
