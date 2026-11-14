---
slug: evaluate-an-ai-gateway-in-an-afternoon
image: /img/blog/og/evaluate-an-ai-gateway-in-an-afternoon.png
title: "Evaluate an AI gateway in an afternoon: a hands-on test plan"
tags: [product, engineering]
description: "A test plan you can run on your laptop with the Docker demo: one request, a policy block, a budget stop, a failover drill and the audit trail. Five checks, each with a clear pass or fail."
---

Feature lists are easy to write and hard to compare. A better way to judge an AI gateway is to break things on purpose and watch what it does. This plan takes about two hours. It uses the OpenProxyAI demo, which runs on your machine with no provider key and no cost. Each step has a command to run and a result that means pass. The same steps work as a checklist for any gateway you are considering.

{/* truncate */}

![Five checks in order: send a request, trigger a policy block, hit a budget limit, run a failover drill, read the audit trail.](/img/blog/evaluate-an-ai-gateway-in-an-afternoon.svg)

## Before you start

You need Docker. The demo starts its own database, a stand-in model server and the gateway, then sends a first batch of traffic so the console has data. Wait until the traffic container prints that all checks passed.

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

The console is at http://localhost:5173 and the API at http://localhost:8000. Sign in as `admin@example.com` with `DemoPass123!`. These are public demo values, never reuse them. Set two keys and a helper in your shell:

```bash
KEY=opai_dev_demo0001_00000000000000000000000000demo01fea5
INTERN=opai_dev_demo0002_00000000000000000000000000demo02741f
chat() { curl -si localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $1" -H 'Content-Type: application/json' \
  -d "{\"model\":\"openai/gpt-4o-mini\",\"messages\":[{\"role\":\"user\",\"content\":\"$2\"}]}"; }
```

The stand-in model server echoes your prompt, so ignore answer quality and latency numbers here. You are testing control, not intelligence.

## Check 1: one endpoint, one key (15 minutes)

```bash
chat $KEY "Explain our refund policy in one line." | grep -iE '^HTTP|x-openproxyai-(model|cache|cost)'
chat $KEY "Explain our refund policy in one line." | grep -iE '^HTTP|x-openproxyai-cache'
```

Use a sentence of your own. The startup traffic already sent a few prompts, and a repeat of one of those would be a cache hit on the first try.

**Pass:** the first call returns 200 and headers that name the model, the cost and the cache result (a miss). The identical second call reports a cache hit. Then open **Request logs** in the console and find both rows with model, tokens and cost.

The question behind this check: could your application switch to this gateway by changing a base URL and a key? See [Migrate to a gateway in three lines](/blog/migrate-to-a-gateway-in-three-lines).

## Check 2: a policy block (20 minutes)

```bash
chat $KEY "What is the status of project-phoenix?" | head -1
chat $KEY "Customer SSN is 123-45-6789, draft the email." | head -1
```

**Pass:** both return HTTP 446, the status OpenProxyAI uses for a policy refusal, and the body gives a reason code and a plain sentence. In **Request logs**, open a blocked row and choose **Open full trace**. The trace should stop after the policy step, with no call to a provider.

Then prove it from the other side. The stand-in server records every request that reaches it. Count before and after:

```bash
calls() { curl -s localhost:9090/__calls | grep -o '"model"' | wc -l; }
calls
chat $KEY "What is the status of project-phoenix?" | head -1
calls
```

**Pass:** the count is the same before and after the blocked request. A gateway that checks policy after calling the provider fails this check, because the data has already left.

## Check 3: a budget that stops spend (20 minutes)

The demo has a user, the intern, with a one cent daily budget. A request containing the marker `[big-usage]` makes the stand-in server report a costly answer. The startup traffic already sent one, so the intern's day is spent. Ask for something new:

```bash
chat $INTERN "One more question." | grep -iE '^HTTP|limit'
```

**Pass:** the call returns 429 and the body names the limit that was reached, here the user's daily budget. In **Request logs**, find the intern's earlier 200 and the refusal after it. Check with the call counter from Check 2 that the refused request never reached the stand-in server. Daily budgets reset at midnight UTC.

The question behind this check: does the limit fail closed, and does the refusal say which limit it was? See [Budgets that fail closed](/blog/budgets-that-fail-closed).

## Check 4: a failover drill (30 minutes)

Failover is the feature everyone claims and few people test. The demo can fake a failing model. A model named `fail-500` makes the stand-in server return an error, and the request header for a backup model tells the gateway where to go next.

```bash
curl -si localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"model":"openai/fail-500","messages":[{"role":"user","content":"hello"}]}' | head -1

curl -si localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -H 'x-openproxy-fallback-model: openai/gpt-4o-mini' \
  -d '{"model":"openai/fail-500","messages":[{"role":"user","content":"hello"}]}' \
  | grep -iE '^HTTP|x-openproxyai-model'
```

**Pass:** the first call, with no backup named, fails. The second returns 200, and the model header shows the backup model served it. Your application saw one successful response.

Now think beyond the demo. With real provider keys you would also test what happens when several keys of one provider are unhealthy, and whether failover stays inside the models and regions you approved. Those are the questions in [Provider failover explained](/blog/provider-failover-explained) and [Retry storms](/blog/retry-storms-recover-from-a-provider-outage).

## Check 5: read the audit trail (30 minutes)

Go back to **Request logs** and take the role of an auditor who knows only the request id.

- Can you find the blocked requests and see the reason code and the rule that fired?
- Does the budget refusal show up, with the user it applied to?
- Is the prompt text absent from the log by default? It should be. The log keeps metadata, not conversations.
- Can an admin see who changed settings? Change the policy mode in the console, then look for the change in the admin audit log.

**Pass:** every earlier check left a record you can find in under a minute, and the record is about decisions, not private text. For the full picture, see [An audit trail your auditor can read](/blog/an-audit-trail-your-auditor-can-read).

## Score it

| Check | What passing means | Result |
|---|---|---|
| 1. One endpoint | Switching needs a base URL and key change only | |
| 2. Policy | Block happens before the provider is called, with a clear reason | |
| 3. Budget | Spend stops, and the refusal names the limit | |
| 4. Failover | A failing model is covered by the backup you named | |
| 5. Audit | Each decision is findable and holds no prompt text | |

Run the same table against every gateway on your shortlist. Pay most attention to the rows where a product needs a long explanation instead of a command.

## What to do after the demo

1. Repeat checks 1 to 4 against your own provider key in a staging deployment. See [Deploy in your VPC in minutes](/blog/deploy-in-your-vpc-in-minutes).
2. Add the things the demo cannot show: single sign-on, your own policy rules in log-only mode, your own data classes.
3. Ask each vendor for the audit export your auditor would receive.
4. Write down what each check cost you in time. That is a real number for the decision.

## Good to know

The demo is a sandbox with a stand-in model server, public credentials and one organization. It proves the controls work, and it says nothing about provider quality, latency or cost. Reset it any time with the down command and the volumes flag, so you can repeat the plan from a clean start.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If the plan finds a gap, star the repo or open an issue so we can look at it.

## Sources

- OpenProxyAI docs: [Quickstart](/getting-started/quickstart), [Policies and guardrails](/core-concepts/policies-and-guardrails), [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets), [Provider routing](/core-concepts/provider-routing), [Chat completions](/api-reference/chat-completions), [Audit logging](/security/audit-logging).
- On this blog: [Migrate to a gateway in three lines](/blog/migrate-to-a-gateway-in-three-lines), [Budgets that fail closed](/blog/budgets-that-fail-closed), [Provider failover explained](/blog/provider-failover-explained), [Retry storms](/blog/retry-storms-recover-from-a-provider-outage), [An audit trail your auditor can read](/blog/an-audit-trail-your-auditor-can-read), [Deploy in your VPC in minutes](/blog/deploy-in-your-vpc-in-minutes).

These statements are based on OpenProxyAI's behavior and docs as of October 27, 2026.
