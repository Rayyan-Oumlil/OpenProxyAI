---
title: Capturing traffic for evaluation
description: Opt in to keeping a redacted sample of prompts and answers, so changes can be judged against real traffic.
---

# Capturing traffic for evaluation

To judge whether a prompt or model change is better, you need real examples. OpenProxyAI normally keeps request metadata only: model, tokens, cost, status, policy decision. It does not keep what users typed. **Payload capture** is an opt-in that keeps a redacted sample of prompts and answers for evaluation.

It is off by default and stores nothing until you turn it on.

## Turn it on

Set a sample rate between 0 and 1 in the policy. `0` (the default) stores nothing, `1` keeps every eligible request, `0.1` keeps about one in ten.

```bash
curl -X PATCH https://your-gateway/api/v1/organizations/current/policy \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"payload_capture_sample_rate": 0.1}'
```

Policy changes take effect within 60 seconds. Only admins can change it, and the change is recorded in the admin audit log.

## What is stored

For each sampled request: the messages (role and text only), the answer, and a `redacted` flag.

- **PII is replaced before anything is written.** The same detector the policy uses finds email addresses, SSNs and payment card numbers and replaces them with `[REDACTED]`. If it replaced anything, the row is flagged `redacted`, and datasets will refuse to import it.
- **Only role and content are kept.** Tool calls, tool results and other message fields are dropped. Images and other non-text parts become a marker such as `{"type": "omitted", "was": "image_url"}`.
- **Each field is capped** at 50,000 characters and marked `[truncated]` if cut.
- **Streamed requests are stored too**, with the text that was streamed.

## What is never stored

- **Anything above the data-class ceiling.** Requests classified above `PAYLOAD_CAPTURE_MAX_DATA_CLASS` (an operator setting, default `internal`) are never kept, whatever the sample rate. A request that raised its own class to `confidential` or `secret`, by header or because it contained an SSN, is not kept.
- **Requests that were refused or failed.** Only answers that were delivered are captured.
- **Anything when the rate is 0.**

## How long it is kept

Each row expires with your plan's audit retention (7 days on the free plan, 30 on starter, 90 on growth, 365 on enterprise). A job runs every six hours and deletes expired rows.

## Failure never affects your traffic

Capture runs in the background after the response is built. If it fails, the failure is logged and the request is unaffected.

## Who can see it

Captured rows are protected by the same row-level security as the rest of your data: one organization cannot read another's. The next slices of the evaluation loop (datasets and evaluators) will be the only readers.
