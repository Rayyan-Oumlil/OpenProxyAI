---
slug: when-to-use-the-batch-api
image: /img/blog/og/when-to-use-the-batch-api.png
title: "When to push LLM work into the batch API, and what changes when you do"
tags: [engineering, product]
description: When a pile of LLM calls belongs in a batch job instead of a loop, and how OpenProxyAI's batch API gives that work a start, an end, a cost ceiling and full policy coverage on every line.
---

Some LLM work does not need an answer in two seconds. Summarizing last quarter's tickets, tagging a document archive, running a prompt over a test set: these are piles of calls, and nobody is waiting on any single one. A script with a loop works until it hits a rate limit, forgets what it already paid for, or keeps going after the budget is gone. A batch job gives that pile a start, an end and a cost ceiling.

This post covers when a batch is the right shape, and what OpenProxyAI's batch API does with each line. The key idea: the gateway runs every line itself, so every line gets the same policy, routing and audit treatment as live traffic.

{/* truncate */}

![Diagram of a batch's life: validating, in_progress, then completed, budget_exceeded, cancelled or failed, with the cost cap leading to budget_exceeded.](/img/blog/when-to-use-the-batch-api.svg)

## When a batch is the right shape

| Question | Batch fits | Keep it live |
|---|---|---|
| Latency tolerance | Minutes to hours is fine | A person is waiting |
| Volume | Hundreds to thousands of similar calls | One call at a time |
| Retries | You can resubmit the few that fail | You need an immediate retry per call |
| Cost visibility | You want to say "this job may spend at most X" up front | Spend per call is small and steady |
| Output | One file you read later | A streamed answer |

The cost row is the one people underrate. A loop has no natural ceiling. A batch has one, because you declare it before anything runs.

## How it works

The API follows the familiar OpenAI shape for files and batches. You authenticate with an API key that has the `proxy:llm` permission. The details are in [the batch API reference](/api-reference/batches).

1. **Upload a file.** `POST /v1/files` with `purpose=batch`. The whole file is checked before anything runs, and a problem is named by line, so you fix it before spending anything.
2. **Create the batch.** `POST /v1/batches` with the file id and an optional `max_cost_usd`.
3. **Poll it.** `GET /v1/batches/{id}` returns the status, request counts and the cost so far.
4. **Read the results.** When it ends, the output file holds one line per request that ran.

Each input line is a chat completion request with a `custom_id` of your choosing, so results are easy to match back to your data.

### Every line gets the full treatment

Each line goes through the same path as live traffic: your organization's policy, data classification, routing, metering and an audit row tagged as coming from a batch. Policy is evaluated per line, so a policy change takes effect mid-batch. Daily budgets are checked as the batch runs, so a batch is not a way around the limits live traffic is held to. See the [request pipeline](/core-concepts/request-pipeline).

### The cost cap

You declare `max_cost_usd` up front. Once the job's cost reaches it, no new line starts and the job ends as `budget_exceeded`. Lines already running finish, and everything that completed is delivered and kept. A batch cannot quietly run away with your money.

### Failed lines are results

A line that is refused by policy or fails at the provider is recorded as a result for that line, and the rest of the batch carries on. A policy block is recorded with status 446. The batch still ends `completed`, and the counts tell you how many lines succeeded.

### Visibility and control

An admin can open **Batch jobs** in the console to see progress and cost for every job in the organization, without seeing any content, and cancel one that is running. See [Batch jobs](/admin-console/batch-jobs). Finished lines are kept, and every admin cancel is written to the [audit log](/security/audit-logging). The owner can also cancel through the API.

## A worked example

Three requests in `requests.jsonl`. If your policy blocks something in one of them, that line comes back as a refusal and the other two are unaffected.

```json
{"custom_id": "ticket-101", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "Summarise this ticket in one sentence: printer offline since Monday."}], "max_tokens": 60}}
{"custom_id": "ticket-102", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "Summarise this ticket in one sentence: VPN drops every hour."}], "temperature": 0.2, "max_tokens": 60}}
{"custom_id": "ticket-103", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "Summarise this ticket in one sentence: new laptop request."}], "max_tokens": 60}}
```

Upload it, then start the batch with a cap of 2 dollars:

```bash
curl https://your-gateway/v1/files -H "Authorization: Bearer $KEY" -F purpose=batch -F file=@requests.jsonl

curl https://your-gateway/v1/batches -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"input_file_id": "FILE_ID", "max_cost_usd": 2}'
```

Poll `GET /v1/batches/BATCH_ID` until the status is an end state, then fetch `GET /v1/files/OUTPUT_FILE_ID/content`. A refused line has `"response": null` and an `error` with `status_code` 446. To retry lines that failed, build a new file from the `custom_id` values that carry an error.

## Good to know

Input and output files hold real text so the batch can send what you wrote and return what the model said. They are removed when they expire, or immediately when you delete them through the files API.

## What to do now

- Put work in a batch when nobody waits on it and you can say how much it may cost.
- Set `max_cost_usd` from your own estimate.
- Check the end status. `budget_exceeded` means the cap stopped the job, so some lines are not in the output file.
- Start with a small file to see the shape of the results, then scale up.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If batches fit your workload, star the repo or open an issue with what you would like to run through them.

## Sources

- [Files and batches API reference](/api-reference/batches): input format, output file.
- [Batch jobs in the console](/admin-console/batch-jobs): progress, cost and cancel.
- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets): the limits live requests are held to.
- [Request pipeline](/core-concepts/request-pipeline): what each live request passes through.

These statements are based on OpenProxyAI's behavior at the post date.
