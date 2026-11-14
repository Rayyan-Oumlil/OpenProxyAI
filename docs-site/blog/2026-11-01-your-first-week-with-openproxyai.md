---
slug: your-first-week-with-openproxyai
image: /img/blog/og/your-first-week-with-openproxyai.png
title: "Your first week with OpenProxyAI: a five-day rollout plan"
tags: [product, engineering]
description: "A practical plan for adopting an AI gateway in five working days: run the demo, set up keys and teams, watch policy in log-only mode, add budgets and routing, then enforce and review."
---

Adopting a gateway sounds like a quarter-long project. It does not have to be. The risky part is not installing it, it is switching on rules that block real work. This plan spreads the rollout over five working days, and each day ends with something you can show to your team. It uses features that already ship, in an order that keeps surprises small.

{/* truncate */}

![A five-day timeline: day 1 run the demo, day 2 create keys and teams, day 3 turn on policy in log-only mode, day 4 set budgets and routing, day 5 enforce and review.](/img/blog/your-first-week-with-openproxyai.svg)

## The idea behind the order

Every step either adds visibility or adds a rule. Visibility comes first, because you cannot set a sensible rule for traffic you have not seen. Rules come in two stages, record first and block second, so the day you start blocking is the day you already know what will be blocked.

## Day 1: run the demo and see the idea

Start on your laptop, not in production. The demo runs the whole stack with seeded data, and it needs Docker but no provider key and no spend. The model behind it is a stand-in server.

Open the console and look for four things:

- A request that mentions a protected project name is blocked before it reaches the model.
- A request with personal data is blocked too. Both use the policy block status, 446.
- A user with a tiny daily budget runs out of it, and the next request is refused.
- A registered tool server shows pinned tool definitions, including one that changed after approval and is flagged for review.

The demo's login details are public demo values, so never reuse them anywhere real. By the end of day 1 your team has seen the product's shape, and you know which of those four scenarios matter most to you.

## Day 2: keys and teams

Now set up the real structure, on a deployment you control. The deployment guide covers Docker Compose and Kubernetes. If you want your own environment first, see [deploy in your VPC in minutes](/blog/deploy-in-your-vpc-in-minutes).

1. Register your organization and sign in to the console.
2. Create an API key for the proxy. Keys are shown once, so store them in a secret manager.
3. Create a team for each group that will spend money, such as engineering, support and data. A team can carry a monthly budget.
4. Invite people. The console creates an invite link and shows it to you. It does not send the email, so share the link yourself.
5. If you use single sign-on, plan it now. See [SSO and SCIM for AI access](/blog/sso-and-scim-for-ai-access).

Then move one low-risk application. Because the gateway speaks the OpenAI API, that is a base URL and a key change, as shown in [migrate to a gateway in three lines](/blog/migrate-to-a-gateway-in-three-lines). Tie its key to a team, or send the team id header, so its cost is attributed from the first request.

End of day 2: one real application is flowing through the gateway, and the request log shows who sent what, with cost and latency.

## Day 3: policy in log-only mode

Policy is where teams get nervous, so do it in a mode that cannot block anyone. Pick log only for the whole policy, then turn on the checks you care about: personal data detection, blocked keywords, prompt injection detection, and a model allowlist if you have one.

In log-only mode, violations are recorded as policy events and no request is blocked. Let it run on real traffic for the rest of the day, or overnight, and read the hit counts per rule from the console or the analytics API. Two readings matter:

- A rule that fires a lot on legitimate traffic is too broad. Narrow it.
- A rule that never fires may not be written the way you meant. Test it with a known example.

This is the same approach described in [roll out guardrails without breaking teams](/blog/roll-out-guardrails-without-breaking-teams). If you work in a regulated industry, compliance templates are a faster starting point. They ship guardrail settings, not certifications, so review the result.

End of day 3: a written list of what each rule would have blocked, and what you changed to fix false positives.

## Day 4: budgets, limits and routing

With attribution working and policy tuned, add the controls that protect your bill and your uptime.

- **Team budgets.** A team that reaches its monthly budget gets a clear 429 response that names the limit. The organization budget is checked independently. See [budgets that fail closed](/blog/budgets-that-fail-closed).
- **Team rates.** Set a per-minute ceiling on requests and tokens for teams, so one noisy job cannot starve the others.
- **Provider keys.** Add more than one key for a provider and give them weights. If a key is rate-limited or failing, traffic shifts to the healthy ones without client changes. See [provider failover explained](/blog/provider-failover-explained).
- **Routing by sensitivity.** Register your models in the model registry with the data classes they are cleared for, then run routing in preview mode. It records which model would have served each request, without refusing anything.

End of day 4: every team has a budget, you have a fallback key, and the preview shows how sensitive requests would route.

## Day 5: enforce and review

Switch the policy from log only to enforce, now that you know what it will do. Do it in the morning, so you can watch the first hours of traffic. If one rule worries you, go back a step and keep the whole policy in log-only while you adjust, since the mode applies to the policy as a whole.

Then review:

- Read the request log and the policy events for the first hours of enforcement.
- Check that blocked requests carry a reason your developers can act on.
- Turn on budget alerts through webhooks so finance hears about spend before the limit does.
- Move routing from preview to enforce once the preview looks right.
- Before you change a model or prompt, test it. See [test a model change before you ship it](/blog/test-a-model-change-before-you-ship-it).

End of day 5: guardrails are enforced, budgets are live, and your team has a routine for changes.

## What to do now

- Pick the five days, and name one owner per day.
- Choose the first application to move, ideally a low-risk internal tool.
- Decide who reviews policy hits on day 3.
- Write your team budgets before day 4, not during it.
- Keep a short note of what changed each day. It becomes your first audit story.

## Good to know

The console creates invite links but does not email them, so send them through your own channel. Policy changes take effect shortly after you save, because policies are cached for a short time.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

It needs Docker and no provider key. The console is at http://localhost:5173. That is day 1 done. If you follow the plan, star the repo or open an issue about where it slowed you down.

## Sources

- [Quickstart](/getting-started/quickstart): registering, creating a key and sending a first request.
- [Managing your organization](/admin-console/managing-your-organization): teams, invites, policy and the log-only to enforce rollout.
- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets): what each limit does and what a refused request returns.
- [Provider routing](/core-concepts/provider-routing): weights and failover.
- [Policies and guardrails](/core-concepts/policies-and-guardrails): the checks you can turn on.
- [Deployment guide](/guides/deployment): running it in your own environment.

These statements are based on the OpenProxyAI documentation and the product's behavior at the post date.
