---
title: Datasets
description: /api/v1/datasets — curated sets of prompts to test changes against, built from captured traffic or by hand.
---

# Datasets

A dataset is a named set of prompts, optionally with the answer each should produce. It is what you test a prompt or model change against. You build one from the traffic you captured with [payload capture](/guides/payload-capture), or by hand.

```
/api/v1/datasets
```

Everything here is **admin only** (a JWT from an organization admin) and recorded in the admin audit log as `dataset.created`, `dataset.imported` and `dataset.deleted`. A dataset belongs to one organization; another organization cannot see it, and asking for its id returns 404.

## Endpoints

| Method | Path | |
|---|---|---|
| `POST` | `/api/v1/datasets` | Create. Body: `{"name": "...", "description": "..."}`. 409 `dataset_exists` if the name is taken. |
| `GET` | `/api/v1/datasets` | List, with each one's `item_count`. |
| `GET` | `/api/v1/datasets/{id}` | One dataset. |
| `DELETE` | `/api/v1/datasets/{id}` | Delete it and all its items (204). |
| `POST` | `/api/v1/datasets/{id}/import` | Copy captured requests in. See below. |
| `POST` | `/api/v1/datasets/{id}/items` | Add one item by hand. |
| `GET` | `/api/v1/datasets/{id}/items` | List items. `limit` (1 to 200, default 50) and `offset`. |
| `DELETE` | `/api/v1/datasets/{id}/items/{item_id}` | Delete one item (204). |

## Importing captured traffic

```json
{
  "model": "openai/gpt-4o-mini",
  "since": "2026-11-01T00:00:00Z",
  "score_name": "thumbs",
  "min_score": 1,
  "limit": 200,
  "order": "random"
}
```

Every field is optional. `model` keeps requests answered by that model. `since` and `until` bound when the request was captured. `score_name` with `min_score` and/or `max_score` keeps requests whose [feedback](/api-reference/feedback) falls in that range, so `thumbs` with `min_score: 1` imports only answers users liked. `limit` is 1 to 1000 (default 100). `order` is `latest` (default) or `random`, for a spread across time.

```json
{"imported": 12, "skipped_redacted": 3, "skipped_duplicate": 0, "stopped_at_capacity": false}
```

- **Rows with personal data are never imported.** A request is skipped if the detector replaced anything when it was captured (`skipped_redacted`), and every row is scanned again on the way in, so a detector that has improved since still catches it.
- **Importing twice adds nothing.** A request already in the dataset is counted in `skipped_duplicate` and does not use up the limit, so repeating a limited import moves on to requests it has not copied yet.
- **A dataset holds at most 10,000 items.** `stopped_at_capacity` is true when the limit stopped an import short.

## Adding an item by hand

```json
{
  "messages": [{"role": "user", "content": "What is the capital of France?"}],
  "expected": "Paris"
}
```

`messages` is 1 to 50 messages with role `system`, `user` or `assistant` and text content. `expected` is optional and is what exact-match and regex evaluators compare against.

An item that contains personal data is **refused with a 422 `pii_in_item`**, naming the kinds found. It is not silently rewritten, because changing an expected answer would quietly change what the test checks. Remove or replace the data and send it again.

## Retention

An imported item is a copy. It does **not** expire with the captured payload it came from; it stays until you delete the item or the dataset. Datasets are curated, so decide what belongs in one. Deleting a dataset deletes its items.
