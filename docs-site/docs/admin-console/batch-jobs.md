---
title: Batch jobs
description: See every batch your applications started, follow its progress and cost, and cancel one that is still running.
---

# Batch jobs

Applications start batches through the [batch API](/api-reference/batches): upload a JSONL file, then create a batch. **Batch jobs** (under Govern in the console) is where an admin sees them all. Only admins can open it.

Every line in a batch already ran under your policy, routing and budget. This page shows progress and cost, **never the content** of any request or answer.

## What each row shows

| Column | Meaning |
|---|---|
| Status | Validating, Running, Completed, Failed, Cancelled, or Stopped at the cap |
| Started by | The user whose key created the batch (or "Deleted user") |
| Lines | A progress bar and `done / total`, with the number that failed |
| Cost / cap | Spend so far against the `max_cost_usd` the application set |
| Started | When it was created |
| Note | The reason, if a job failed or stopped |

"Stopped at the cap" means the batch reached its own `max_cost_usd` and no further lines were run.

While any job is running the page refreshes every 5 seconds. With nothing running it makes no requests. A screen reader hears one short status sentence ("2 batch jobs are running") that updates without moving focus.

## Cancel a job

Choose **Cancel** on a running job and confirm. Lines already finished are kept and billed; the rest are not run. Cancelling a job that has already ended is refused (409), and every cancellation is written to the [admin audit log](/security/audit-logging) as `batch_job.cancelled`.

## Use the API

```
GET  /api/v1/batch-jobs?limit=50
POST /api/v1/batch-jobs/{job_id}/cancel
```

`limit` is 1 to 100 and jobs come back newest first. Both calls need an admin session token.
