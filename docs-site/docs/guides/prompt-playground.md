---
title: Prompt Playground
description: Compare models side-by-side and version your prompt templates.
---

# Prompt Playground

The admin console includes a playground for comparing models side-by-side and managing reusable prompt templates.

## Comparing models

```
POST /api/v1/playground/compare
```

Send the same prompt to multiple models in one call and compare time-to-first-token, total latency, token counts, and cost side-by-side — useful for deciding which model to default a use case to before committing to it in production.

## Prompt templates

Templates let you save and version a prompt so application code can reference it by ID instead of embedding raw prompt text.

```
GET  /api/v1/prompt-templates
POST /api/v1/prompt-templates
GET  /api/v1/prompt-templates/{template_id}/versions
```

Every edit to a template creates a new version rather than overwriting the previous one, so you can roll back or diff behavior across versions.

## Experiments

For structured A/B testing of prompts or models against real traffic, see the experiments API:

```
POST /api/v1/experiments
POST /api/v1/experiments/{experiment_id}/start
GET  /api/v1/experiments/{experiment_id}/results
```
