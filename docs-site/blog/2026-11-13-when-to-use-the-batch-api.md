---
slug: when-to-use-the-batch-api
title: "When to push LLM work into the batch API, and what changes when you do"
tags: [engineering, product]
description: When a pile of LLM calls belongs in a batch job instead of a loop, and what OpenProxyAI's batch API keeps, caps and does not do, read from the code and tests, with a worked example.
---

Some LLM work does not need an answer in two seconds. Summarizing last quarter's tickets, tagging a document archive, running a prompt over a test set: these are piles of calls, and nobody is waiting on any single one. A script with a loop works until it hits a rate limit, forgets what it already paid for, or keeps going after the budget is gone. A batch job gives that pile a start, an end and a cost ceiling.

This post covers when a batch is the right shape, and what OpenProxyAI's batch API does with each line. One thing differs from what you may expect: it does not hand the file to a provider. The gateway runs every line itself.

{/* truncate */}

![Diagram of a batch's states: validating, in_progress, then completed, budget_exceeded, cancelled or failed, with the cost cap leading to budget_exceeded.](/img/blog/when-to-use-the-batch-api.svg)

## When a batch is the right shape

| Question | Batch fits | Keep it live |
|---|---|---|
| Latency tolerance | Minutes to hours is fine | A person is waiting |
| Volume | Hundreds to a few thousand similar calls | One call at a time |
| Retries | You can resubmit the few that fail | You need an immediate retry per call |
| Cost visibility | You want to say "this job may spend at most X" up front | Spend per call is small and steady |
| Output | One file you read later | A streamed answer |

The cost row is the one people underrate. A loop has no natural ceiling. A batch has one, because you declare it before anything runs.

## How it works in OpenProxyAI

The API follows the OpenAI shape for files and batches. You authenticate with an API key that has the `proxy:llm` permission. The details are in [the batch API reference](/api-reference/batches).

1. **Upload a file.** `POST /v1/files` with `purpose=batch`. The whole file is checked before anything runs, and a problem is named by line (422 `invalid_batch_file`).
2. **Create the batch.** `POST /v1/batches` with the file id and an optional `max_cost_usd`.
3. **Poll it.** `GET /v1/batches/{id}` returns the status, `request_counts` and `cost_usd`. The statuses are `validating`, `in_progress`, `completed`, `failed`, `cancelled` and `budget_exceeded`.
4. **Read the results.** When it ends, `output_file_id` names a JSONL file, one line per request that ran.

Each input line is `custom_id`, `method`, `url` and `body`. Only `POST` to `/v1/chat/completions` is accepted. The body may hold `model` (written `provider/name`), `messages` (text only) and optionally `temperature` and `max_tokens`. Anything else, including streaming and tools, is refused instead of ignored.

### What each line goes through

The batch service calls the same model runner that evals and the playground use. For each line that means the organization's policy, data classification, routing, metering and an audit row, tagged with `source: batch` and the batch id. The policy is read again for every line, so a policy change takes effect mid-batch. The owner must still be active.

Before each line, the service checks the organization's daily budget and the owner's daily budget. If either is used up, the batch stops with `budget_exceeded` and says why. A batch is not a way around the limits live traffic is held to.

### The cost cap

`max_cost_usd` defaults to 5 and can be at most 500 (set by `BATCH_DEFAULT_MAX_COST_USD` and `BATCH_MAX_COST_USD`). After each line, the job's total cost is compared to the cap. At or over it, no new line starts and the job ends `budget_exceeded`. Lines already running finish. With 4 lines in flight at once, the overshoot is at most the cost of those lines. A test with 1 dollar lines and a 2.5 dollar cap checks this bound, and checks that what finished is still delivered.

### Limits, from the code

| Limit | Value |
|---|---|
| Lines per file | 5,000 |
| Size of one line | 256 KB |
| File size | 16 MB |
| Lines running at once | 4 |
| Active batches per organization | 2 (a third gets 409 `too_many_batches`) |
| Files kept per user | 50 |
| File retention | 7 days by default (`BATCH_FILE_RETENTION_DAYS`) |

### Failed lines, cancel, results

A line that fails or is refused is a result, never a failure of the batch. A policy block is recorded with status 446. A provider error is recorded with status 502. Both count in `failed`, and the batch still ends `completed`.

An admin can open **Batch jobs** in the console to see progress and cost for every job in the organization, without seeing any content, and cancel one that is running. See [Batch jobs](/admin-console/batch-jobs). Finished lines are kept and billed. Every admin cancel is written to the [audit log](/security/audit-logging). The owner can also cancel through `POST /v1/batches/{id}/cancel`. A batch that already ended cannot be cancelled (409).

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

The create call returns the batch with `status: validating`. Poll `GET /v1/batches/BATCH_ID` until the status is an end state. Then fetch `GET /v1/files/OUTPUT_FILE_ID/content`. A successful line has this shape. A refused line has `"response": null` and an `error` with `status_code` 446.

```json
{"id": "batch_req_…", "custom_id": "ticket-101", "response": {"status_code": 200, "body": {"choices": [{"message": {"role": "assistant", "content": "…"}}], "usage": {"total_tokens": 41}}}, "error": null}
```

To retry the lines that failed, build a new file from the `custom_id` values that carry an error. That is a manual step.

## What this does not do

- **No provider batch discount.** The gateway sends each line as an ordinary live call, so each is priced like one. This is on purpose: a provider batch cannot be policed line by line. If a provider's batch pricing matters more to you than per-line policy, this is the wrong tool.
- **No automatic per-line retry.** The batch code makes one call per line. We found no retry logic in it.
- **No request-rate limits inside a batch.** Lines run through the model runner, not the request gate, so the per-minute request and token limits and a team's monthly budget are not checked per line. The daily organization and user budgets are, and so is the cost cap. Four lines at once is the only throttle.
- **`completion_window` is not a deadline.** The field is accepted and the response always shows `24h`. We found no code that enforces it. A batch stuck in progress for six hours is ended as failed by a cleanup job.
- **Text only, chat only.** No streaming, tools or other endpoints.
- **Content is stored.** Input and output files hold real text until they expire or you delete them with `DELETE /v1/files/{id}`.
- **The cost is only as good as the price.** A call the gateway cannot price is charged a flat estimate, so the cap is approximate for such a model.

## What to do now

- Put work in a batch when nobody waits on it and you can say how much it may cost.
- Set `max_cost_usd` from your own estimate. Do not rely on the default.
- Check the end status. `budget_exceeded` means lines are missing from the output file.
- Keep the 4-lines-at-once pace in mind when you plan a 5,000 line job.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173.

## Sources

- [Files and batches API reference](/api-reference/batches): input format, limits, output file.
- [Batch jobs in the console](/admin-console/batch-jobs): progress, cost and cancel.
- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets): the limits live requests are held to.
- [Request pipeline](/core-concepts/request-pipeline): what each live request passes through.

These statements are based on the OpenProxyAI source code, tests and docs as read on November 13, 2026. No provider batch product was examined.
