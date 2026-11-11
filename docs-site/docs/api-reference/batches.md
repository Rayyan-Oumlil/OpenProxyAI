---
title: Files and batches
description: /v1/files and /v1/batches. Run thousands of chat requests as one job, with every line under your policy, routing and audit.
---

# Files and batches

Upload a JSONL file of chat requests and run them as one job. Unlike a provider's own batch API, the gateway runs each line itself through the same path as a live request, so **every line gets your policy, data classification, routing, metering and audit row**, on any provider. Authenticate with an API key that has the `proxy:llm` permission. A file or batch belongs to the user who owns the key.

## 1. The input file

One request per line:

```json
{"custom_id": "q1", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "Summarise Q3."}], "temperature": 0.2, "max_tokens": 200}}
```

The whole file is checked before anything runs, and a problem is named by line (422 `invalid_batch_file`). Rules: up to 5,000 lines, 256 KB a line, 16 MB a file; unique `custom_id` (1 to 64 characters); only `POST /v1/chat/completions`; `body` holds `model` (`provider/name`), `messages` (text only) and optionally `temperature` and `max_tokens`. Streaming, tools and other fields are refused rather than ignored.

```bash
curl https://your-gateway/v1/files -H "Authorization: Bearer $KEY" -F purpose=batch -F file=@requests.jsonl
```

A `Content-Length` header is required and the size is checked before the body is read. You can keep 50 files.

## 2. Start a batch

```bash
curl https://your-gateway/v1/batches -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"input_file_id": "<file id>", "max_cost_usd": 5}'
```

`max_cost_usd` is the **spending cap** (default 5, at most 500). Once reached, no new line starts and the batch ends `budget_exceeded`; lines already running finish, so the overshoot is bounded by the concurrency (4). A batch can never spend more than it declared, plus that. At most 2 batches run at once per organization (409 `too_many_batches`).

`GET /v1/batches/{id}` shows `status` (`validating`, `in_progress`, `completed`, `failed`, `cancelled`, `budget_exceeded`), `request_counts` and `cost_usd`. `GET /v1/batches` lists yours. `POST /v1/batches/{id}/cancel` stops it; what already finished is kept.

## 3. The output file

When the batch ends, `output_file_id` names a JSONL file (`GET /v1/files/{id}/content`), one line per request that ran:

```json
{"id": "batch_req_…", "custom_id": "q1", "response": {"status_code": 200, "body": {"choices": [{"message": {"role": "assistant", "content": "…"}}], "usage": {"total_tokens": 41}}}, "error": null}
```

A line your policy refuses has `"response": null` and `"error": {"status_code": 446, "message": "…"}`; a provider failure is a 502. **A bad line is a result, never a failure of the batch.** Each line also appears in your request log with `source: batch` and the batch id.

## What is kept, and for how long

Input and output files hold real text, because a batch must send what you wrote and give back what the model said. They are deleted after `BATCH_FILE_RETENTION_DAYS` (default 7) by an hourly job, or at once with `DELETE /v1/files/{id}`. Nothing else stores the text. A batch stuck in progress for six hours (the process that held it died) is ended as failed.
