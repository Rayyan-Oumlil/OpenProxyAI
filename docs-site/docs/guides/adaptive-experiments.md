---
title: Adaptive A/B experiments
description: Let an experiment move traffic toward the better variant as feedback arrives, and stop when one is clearly best.
---

# Adaptive A/B experiments

An experiment splits the traffic for one model between variants, for example two models or two settings. Normally the split is fixed until you change it. An **adaptive** experiment reads the [feedback](/api-reference/feedback) your application sends and moves traffic toward the variant people like more, then stops by itself, naming a winner, when one is clearly better.

## Set one up

Create an experiment with `mode: "adaptive"` and the name of the feedback score to judge by.

```bash
curl -X POST https://your-gateway/api/v1/experiments \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "mini vs full",
    "target_model": "openai/gpt-4o",
    "variants": [
      {"model": "openai/gpt-4o-mini", "traffic_weight": 50},
      {"model": "openai/gpt-4o",      "traffic_weight": 50}
    ],
    "mode": "adaptive",
    "metric": "thumbs"
  }'
```

Your application then sends a `thumbs` rating for answers, as described under [Feedback](/api-reference/feedback). The request id ties each rating to the variant that served it.

| Setting | Default | |
|---|---|---|
| `metric` | required | The score to judge by. Its values must be between 0 and 1: `thumbs` (up is 1, down is 0) or any rate. |
| `min_samples_per_variant` | 30 | Nothing is decided until **every** variant has this many ratings. At least 20. |
| `delta` | 0.01 | The test stops when one variant is best with probability at least `1 - delta`. Between 0.001 and 0.2. Smaller is stricter. |
| `weight_floor` | 5 | No variant gets less than this percent of traffic, so one that started badly can still recover. 1 to 20. |

You need at least two variants, and `weight_floor` times the number of variants must not exceed 100.

## What happens

A job runs every five minutes. For each active adaptive experiment it counts the ratings per variant and then:

1. **Before every variant has `min_samples_per_variant` ratings, it changes nothing.** Early data is too noisy to steer by, and a winner is never named this early however lopsided it looks.
2. **After that, traffic follows each variant's chance of being the best one**, never below the floor.
3. **When one variant is best with probability at least `1 - delta`, the experiment stops** and `winner_variant_id` is set with `stopped_reason: "winner"`.

Every weight change and the winner are written to the admin audit log by `system:adaptive-ab`.

**A winner is recorded, not deployed.** Stopping ends the split, so requests go back to the target model, and names the winner. You decide whether to switch. An experiment never changes which model serves your production traffic on its own.

## Reading the results

`GET /api/v1/experiments/{id}/results` reports each variant separately by its id, even when two variants use the same model, with its current `traffic_weight` and, for an adaptive test, `probability_best`. The `adaptive` section shows how far along the test is:

```json
{
  "adaptive": {
    "metric": "thumbs", "ready": false, "min_samples_per_variant": 30, "delta": 0.01,
    "samples": {"<variant id>": 22, "<variant id>": 17},
    "winner_variant_id": null, "stopped_reason": null, "error": null
  }
}
```

`ready` is true once every variant has enough ratings. If the job cannot update a test it leaves it as it was and says why in `error`, for example when the metric has values outside 0 to 1.

## How reliable is the stopping rule

Honestly: good at finding a real difference, and with a known false-alarm rate when there is none.

The rule is checked again and again as ratings arrive, and every extra look gives chance a new opportunity to produce a convincing-looking gap. We measured it by simulation, looking after every 10 ratings per variant and allowing up to 400 each:

| | `delta` 0.05 | `delta` 0.01 (default) |
|---|---|---|
| Variants truly different (70% vs 50% liked): picks the better one | 119 of 120 | 119 of 120 |
| Picks the worse one | 1 of 120 | 1 of 120 |
| Variants truly **equal**: names a "winner" anyway | about 4 in 10 | about 1 in 8 |

That is why the default is `0.01` and not the textbook `0.05`. When the variants really are equal, the false winner costs you nothing, because either choice is as good. If you want fewer false winners on small differences, lower `delta` or raise `min_samples_per_variant`; either makes the test take longer.

## Things to know

- **Only one active experiment per target model** is allowed in an organization.
- **Replacing the variants, or changing the mode or metric, forgets a previous winner**: a result means nothing once the test changes. Replacing variants also means earlier ratings no longer count, because they belong to the old variants.
- **Starting a stopped experiment again clears its winner** and lets the job steer it again.
- **Ratings come from your application.** A test with no feedback never moves.
