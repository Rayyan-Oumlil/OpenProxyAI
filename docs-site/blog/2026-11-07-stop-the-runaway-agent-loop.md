---
slug: stop-the-runaway-agent-loop
title: "Stop the runaway agent loop: budgets and rate limits that act before the invoice"
tags: [product, engineering]
description: "An agent stuck in a loop can burn a month of budget overnight. Give each agent its own key and team, set per-minute and dollar ceilings, and teach the agent to read the 429 that comes back."
---

Agents loop. A tool call fails, the model tries again, the plan never converges, and a few hours later someone notices a bill that was meant to last a month. Better prompts help, but they are not a control. A limit is. The practical goal is simple: when an agent misbehaves, it should hit a ceiling that belongs to it, and the rest of the company should not notice.

{/* truncate */}

![An agent key in a loop passes first through its team limits, per minute and per month, then through the organization limits, per day and per minute. When a limit is reached the gateway answers 429, the body names the limit type, and a wait time says when to retry. Other teams keep working, and cost by key shows which agent looped.](/img/blog/stop-the-runaway-agent-loop.svg)

## Why loops are expensive

A normal chat call is one request. An agent run can be hundreds, and each step usually re-sends a growing history. Three failure patterns show up again and again.

- **The retry loop.** A tool returns an error, the agent calls it again with the same input, and nothing changes.
- **The plan that never ends.** The agent keeps decomposing a task into smaller tasks, each costing tokens.
- **The fan-out.** One run spawns several sub-agents, and each of them loops.

All three share a trait: the cost grows with time, and nobody is watching. So the control has to be automatic and it has to sit outside the agent, because an agent that is stuck cannot be trusted to stop itself.

## Give every agent its own boundary

The most useful step costs nothing: **one key per agent, and each key tied to its own team.** Then everything the agent spends is counted against that team, and the team's ceilings stop it without touching anyone else.

OpenProxyAI checks several limits together on every request, before any provider call. The first one reached refuses the request.

| Layer | What it caps |
|---|---|
| Team | A monthly dollar budget, and requests and tokens per minute, counted separately for each team. |
| User | A daily dollar budget for one user. Give an agent its own service user to get a ceiling for that agent alone. |
| Organization | Requests and tokens per minute, and a daily dollar budget, for everything together. |
| Model | Optional per-model rate limits set in the policy. |

A request must pass every layer that applies. So an agent can use only what its own team allows, and all teams together stay inside the organization's limits. Dollar budgets for the day reset at midnight UTC.

Tool calls are limited too. Each API key has its own request limit for the tool gateway, counted apart from your model quota, so a looping agent cannot hammer your tools without end.

## What the agent gets back

When a limit is reached, the response is HTTP `429` with a `Retry-After` header. The body names which limit it was, in a field called `limit_type`, for example requests per minute or a team's monthly budget. This matters because the right response differs.

| What was reached | What the agent should do |
|---|---|
| A per-minute limit | Wait for the time given, then continue. This is a pause, not a failure. |
| A daily or monthly budget | Stop. Waiting a few seconds will not help. Report to a person, or park the work until the budget resets. |

Match on the limit type, not only on the status code. An agent that treats every `429` as "try again in a moment" will sit in a retry loop against a budget that cannot recover, which is the same loop you were trying to stop. One more detail worth knowing: every request counts toward the request limit, including ones that are refused. A tight retry loop therefore keeps itself locked out. Back off with some random jitter, and give up after a few tries.

A streamed request is checked before it starts. If its estimated cost is more than what is left of the day, it is refused with a `402` instead of starting and being cut off halfway.

## See it, and get warned

Limits are the safety net. Visibility is how you learn from the fall.

- The dashboard has cost by team, by API key and by user, so the key that looped is one click away.
- Request logs show each call with its model, cost and outcome, and can be filtered by team.
- A budget alert goes to your webhook when daily spend reaches 80 percent of the organization's daily budget, so you hear about it before the wall, not after.

## A worked scenario

A platform team runs three agents: a support triager, a nightly report builder and a coding assistant for the data team. Each has its own key, and each key is tied to its own team with a monthly budget and per-minute limits that fit its job.

1. At 2 a.m. the report builder hits a malformed file and starts retrying the same step.
2. Its team's per-minute limit is reached within moments. The agent receives `429` responses that name the limit and a wait time. Its client backs off with jitter.
3. It keeps going at a slower rate until the team's monthly budget is reached. The responses now name a budget. The agent is written to stop on those, so it parks the job and posts a note.
4. The support triager and the coding assistant never notice. They have their own ceilings and their own headroom.
5. In the morning, cost by key shows which agent used the budget, and the request log shows the repeated call. The fix is a one-line change to the step, not an incident review.

## What to do now

1. Create one API key per agent and tie each to a team.
2. Set a monthly budget and per-minute limits for each team. Start tight, and loosen with data.
3. Give long-running agents their own service user so a daily dollar ceiling applies to them alone.
4. Teach every agent client to read `Retry-After` and the limit type. Pause for rate limits, stop for budgets.
5. Cap retries and concurrency in the agent itself. A limit at the gateway is the backstop, not the plan.
6. Add a webhook for the budget alert and send it somewhere a person will see it.
7. Review cost by key weekly for a month, then adjust.

## Good to know

Spend is added after a call finishes, so requests already running when a budget is reached still complete. The overshoot is bounded by what runs at the same moment, which is why running one agent per team, with its own budget, keeps it small. Related reading: [budgets that fail closed](/blog/budgets-that-fail-closed), [rate limiting LLM traffic](/blog/rate-limiting-llm-traffic), [bounding a hijacked agent](/blog/bounding-a-hijacked-agent) and [putting coding agents behind a gateway](/blog/put-coding-agents-behind-a-gateway).

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

You need Docker and no provider key. The console is at http://localhost:5173. If it helps, star the repo or open an issue with the limit you would like to see.

## Sources

- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets): the layers, the `429` body and the daily reset.
- [API keys and provider keys](/api-reference/keys): tying a key to a team.
- [Organizations, teams and users](/api-reference/organizations-teams-users): team budgets and user budgets.
- [Errors and status codes](/api-reference/errors-and-status-codes): `429` and `402`.
- [MCP gateway](/guides/mcp-gateway): the per-key limit for tool calls.

The statements above are based on these sources and on OpenProxyAI's behavior at the post date.
