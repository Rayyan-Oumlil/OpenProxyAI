---
slug: answers-from-models-without-a-price
title: "Never lose a model's answer because you cannot price it"
tags: [engineering, architecture]
description: A gateway that fails a call because it cannot compute the cost throws away an answer that was already paid for. What we changed, why an estimate beats an error, and the limits of a flat fee.
---

A provider answers your request. The tokens are generated and billed. Then your gateway tries to work out what the call cost, cannot find the model in its price list, and returns an error. The answer is gone, the money is spent, and the caller sees a failure. We shipped exactly that bug for batch lines, eval runs and conversation turns. This post explains the fix and the trade-off behind it.

{/* truncate */}

![Request path: provider call, then price the call, then audit log. Before: pricing raises, the row is logged as 502 and the answer is thrown away. After: a flat fee is charged, the answer is returned, the row is logged as 200 with cost_estimated in its metadata.](/img/blog/answers-from-models-without-a-price.svg)

## The problem

OpenProxyAI prices calls with LiteLLM, a library that keeps a table of per-token prices. If a model is not in the table, LiteLLM raises a plain exception.
Chat already handled this: it charged a flat fee and carried on. But the code that calls models from inside the gateway did not. That code, `execute_plan` in `backend/app/services/model_runner.py`, serves batch lines, eval runs and conversation turns. Its price lookup sat inside the same `try` block as the provider call. A pricing exception fell into the error handler, which logged the call as a 502 and returned an error.

Read that order again. The provider had already answered. We discarded a finished answer because of bookkeeping. In a batch, that meant every line to such a model failed.

## How we found it

By running the Python SDK against a real local model (Ollama) through the demo gateway. The model used there was one the gateway could not price. The same live test found a second bug, covered below.

## What happens now

The price lookup is a function that does not raise, `price_or_fallback` in `backend/app/services/cost_tracker.py`. It returns the cost and a flag saying whether it is an estimate:

```python
def price_or_fallback(self, response, call_type=None, units=1) -> tuple[Decimal, bool]:
    try:
        return (self.calculate_cost_usd(response, ...)), False
    except Exception as exc:
        logger.warning("Could not price a %s call: %s", call_type or "chat", exc)
        return Decimal(str(settings.UNPRICED_CALL_COST_USD)) * units, True
```

And `execute_plan` now uses it:

```python
# The provider has answered. A model LiteLLM cannot price is charged the flat fee and marked an estimate, never turned into a failure.
cost, estimated = cost_tracker_service.price_or_fallback(response)
metadata = {**plan.metadata, "cost_estimated": True} if estimated else plan.metadata
```

The result for an unpriced model:

| | Before | After |
|---|---|---|
| Answer returned to caller | No | Yes |
| Audit log status | 502 | 200 |
| Cost recorded | None | Flat fee |
| Marked as estimate | No | `cost_estimated: true` in request metadata |

The flat fee is the setting `UNPRICED_CALL_COST_USD`, default `0.01`, charged per unit (a call, or an image). It is listed in [environment flags](/getting-started/environment-flags). The API docs describe the same behavior under Cost in `docs-site/docs/api-reference/more-endpoints.md`.

## The design choice: open on price, not free

There were three options.

1. **Fail the call** (the old behavior). Safe-looking, but it destroys a result that already exists.
2. **Return the answer and record zero cost.** The caller is happy, but spend is invisible. A model nobody can price becomes a model nobody can budget.
3. **Return the answer and charge a flat fee, flagged as an estimate.** What we do.

The audit logger adds each call's cost to the spend counters (`rl:usd:...` keys in `backend/app/services/audit_logger.py`). Chat budget checks read those same counters. A flat fee means the call moves them. Zero would not. So the rule is: a missing price must not decide whether the user gets the answer, and it must not make the call free.

## A worked example

The regression test in `backend/tests/test_model_runner.py` makes the price function raise "This model isn't mapped yet." and then asserts:

- the outcome has no error and its content is the model's answer (`"4"`),
- the cost equals the flat fee, and the fee is greater than zero,
- exactly one log row exists, with status 200, the flat fee as cost, and `cost_estimated` true in its metadata.

A second test checks the opposite: a priced call has no `cost_estimated` key at all. The flag appears only when it is true, so you can filter on it.

## A second bug, same method

The same live run showed two `X-OpenProxyAI-Request-Id` headers on responses. The request-id middleware (`backend/app/middleware/request_id.py`) added its own id even when a route had already set one. Clients saw `id1, id2`, and `POST /v1/feedback`, which wants a single id, rejected it. The middleware now adds its header only when none is present. Two tests in `backend/tests/test_request_id_middleware.py` check that a route's own id is kept once, and that a response without one gets the middleware's.

Neither bug was visible until a real model answered through the real stack. That is the method worth repeating.

## What this does not do

- **The estimate can be wrong in either direction.** It is a flat fee, not a price. A long answer from an expensive model costs more than 0.01 dollars; a short one from a cheap model costs less. Budgets that include estimated calls are approximate for those calls.
- **It does not find the real price.** The fee is only a stand-in. We did not add per-model price overrides in this change.
- **It does not hide the problem.** A warning is logged and the row is flagged. We did not check whether any console view surfaces `cost_estimated`; it is in the audit metadata.
- **We did not test the stream path live.** The streaming path for conversation turns has its own fallback (`_stream_cost` in the same file), which first tries to price the stream and falls back to the same flat fee. We read it, we did not exercise it.

## What to do now

- Set `UNPRICED_CALL_COST_USD` to something near your typical cost for any model the price table does not list.
- Open a few batch or eval log rows and look for `cost_estimated` in their metadata to see which models are not priced. The log list has no filter for it.
- If you build a gateway: price after the answer, never instead of it, and make the fallback visible.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173.

## Sources

- Commit `2246949` in the OpenProxyAI repository: `backend/app/services/model_runner.py`, `backend/app/services/cost_tracker.py`, `backend/tests/test_model_runner.py`, `backend/app/middleware/request_id.py`.
- [Environment flags](/getting-started/environment-flags): `UNPRICED_CALL_COST_USD`.
- [Rate limiting and budgets](/core-concepts/rate-limiting-and-budgets): how spend is limited.
- [Audit logging](/security/audit-logging): where the request metadata lives.
- [Batch jobs](/admin-console/batch-jobs): the console view for batches.
- Companion post: [what broke when our Python SDK met a real streaming connection](/blog/python-sdk-real-streaming).

These statements are based on the repository code, tests, docs and commit message as of 2026-11-13.
