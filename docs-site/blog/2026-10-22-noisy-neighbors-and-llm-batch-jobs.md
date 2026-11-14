---
slug: noisy-neighbors-and-llm-batch-jobs
image: /img/blog/og/noisy-neighbors-and-llm-batch-jobs.png
title: "Noisy neighbors: keep one team's batch job from starving everyone else"
tags: [product, engineering]
description: "A nightly enrichment job can eat the rate limit that your support chat needs. Here is how team ceilings, organization limits and a batch API with a cost cap keep one workload from crowding out the others."
---

At 9:00 a.m. the support team's chat assistant starts returning errors. Nothing is wrong with it. At 8:55 the data team started a job that sends ten thousand documents through the same model, using the same shared limits. Cloud engineers know this as the noisy neighbor problem: one tenant's heavy work makes the shared resource slow or unavailable for everyone else. LLM traffic has it too, and the fix is the same idea: give each workload its own ceiling, and give heavy work a different lane.

{/* truncate */}

![Two lanes into the gateway. Live traffic from support chat passes team rate ceilings and organization limits. A batch job from the data team enters its own lane with a cost cap and bounded concurrency. Both lanes are metered and audited.](/img/blog/noisy-neighbors-and-llm-batch-jobs.svg)

## Why shared limits fail

Providers limit requests and tokens per minute per account or per key. Your gateway may add its own organization-wide limits. Under a single shared limit, whoever sends the most wins, and everyone else sees `429` errors. Raising the limit helps for a week. Then a bigger job arrives.

Two different things are being mixed up:

- **Interactive traffic** needs low latency and steady access. A person is waiting.
- **Bulk traffic** needs throughput and a cost ceiling. Nobody is waiting on any one call.

If both share one pool, the bulk work always wins, because it never stops asking. For the general theory of limits for LLM traffic, see [rate limiting LLM traffic](/blog/rate-limiting-llm-traffic).

## Layer 1: a ceiling per team

OpenProxyAI counts requests and tokens per minute separately for each team, so a team can only use its own allowance. A request counts toward a team when its key is tied to that team, or when the caller sends the team in a documented header. When a team goes over, only that team's calls are refused. The data team's job can run into its own ceiling without touching the support team's counter.

The same checks also run at the organization level and for each user, so all teams together stay inside the organization's overall limits. The first limit reached refuses the request.

| Scope | What is limited |
|---|---|
| Organization | Requests per minute, tokens per minute, dollars per day |
| User | Dollars per day |
| Team | Requests and tokens per minute, dollars per month |
| Model | Optional requests and tokens per minute for a given model |

## What a team sees when it hits a ceiling

A refused call gets HTTP `429` with a `Retry-After` header and a body that names which limit was reached, for example a team requests-per-minute limit. A well-behaved client reads that name and the wait time, backs off, and tells the user something useful instead of "something went wrong". A streamed request is also checked before it starts, using an estimate of its cost, so a call that cannot be paid for is refused at the door rather than cut off halfway through. If clients retry without waiting, a small problem grows, which [retry storms](/blog/retry-storms-recover-from-a-provider-outage) explains.

## Layer 2: a lane for bulk work

The best protection for live traffic is to take bulk work out of its path. The batch API is built for that. You upload a file of requests, start a batch with a cost cap, and read the results later.

What makes a batch a good neighbor:

- **A cost cap you declare up front.** When the job reaches it, no new line starts and the job ends as over budget. Lines already running finish, so the overshoot is small and bounded.
- **Bounded concurrency.** The gateway runs the lines itself at a controlled pace, so a ten-thousand-line file does not become ten thousand simultaneous calls.
- **A limit on active jobs.** Each organization can run only a couple of batches at once, so a second large job waits instead of piling on.
- **Daily budgets still apply.** Before each line, the gateway checks the organization's and the owner's daily budgets. A batch is not a way around them.
- **Every line is governed.** Each line gets your policy, data classification, routing, metering and an audit row, marked as coming from a batch.
- **Failures are results.** A line that is refused or fails is recorded for that line. The rest of the job carries on.

Admins see every batch in the console, with progress and cost, and can cancel one that is running. They never see the content of the requests. See [batch jobs](/admin-console/batch-jobs) and the [batch API reference](/api-reference/batches).

## A worked scenario

| Team | Workload | Setup |
|---|---|---|
| Support | Live chat | Team key, modest per-minute ceiling sized for peak chat, monthly budget |
| Data | Nightly document enrichment | A batch job each night with a cost cap, run under the data team's service user |
| Interns | Experiments | Tiny monthly budget |

Before: the nightly enrichment ran as a loop in the live lane and used the shared limit up by 9:00. After: the enrichment is a batch with a cap of a few dollars per run. Support keeps its own ceiling and sees no change. If the data team wants the job to finish faster, it asks for a bigger cap, which is a visible decision, not an accident.

If the support team itself goes over its ceiling during an incident, the refusal names the team limit. Nobody has to guess whose traffic caused it.

## What to do now

- [ ] Separate interactive and bulk workloads in your inventory.
- [ ] Give each interactive workload a team and a key tied to it.
- [ ] Set a per-minute ceiling for teams in the organization policy, sized for the busiest realistic hour.
- [ ] Move loops that nobody waits on into batch jobs with a cost cap.
- [ ] Make clients read the limit name and the `Retry-After` value in a `429`.
- [ ] Add the 80 percent budget alert webhook to the channel the platform team watches.

## Good to know

The per-minute team ceiling is a single value in the organization policy, applied to each team's own counter. Teams with different needs can differ on budget, but they share the same rate ceiling. It is set through the policy API; the console shows per-model rate limits. Batch lines are held to the job cost cap, daily budgets and bounded concurrency rather than the per-minute counters, which is why they make a gentle neighbor. Spend is added after a call finishes, so requests already running when a budget is reached still complete.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If it helps, star the repo, and if your workloads need a different shape of limit, open an issue.

## Sources

- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets): the layers, the order of checks, what a refusal contains.
- [Files and batches](/api-reference/batches): cost cap, concurrency, per-line governance.
- [Batch jobs in the console](/admin-console/batch-jobs): progress, cost and cancel for admins.
- [Managing your organization](/admin-console/managing-your-organization): teams, team budgets and the team ceiling.
- [Errors and status codes](/api-reference/errors-and-status-codes): the shared error format.
- On this blog: [rate limiting LLM traffic](/blog/rate-limiting-llm-traffic), [budgets that fail closed](/blog/budgets-that-fail-closed), [bounding a hijacked agent](/blog/bounding-a-hijacked-agent).

These statements are based on the sources above and on OpenProxyAI's behavior as of 2026-10-22.
