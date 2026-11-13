---
title: Health checks
description: Liveness and readiness endpoints for load balancers and Kubernetes probes.
---

# Health checks

Neither endpoint needs authentication.

| Endpoint | Use it as | What it checks |
|---|---|---|
| `GET /health` | Liveness probe | The process is up. Always `200`; it checks no other service. |
| `GET /ready` | Readiness probe | Postgres and Redis both answer. |

```json
{"status": "ready", "postgres": "ok", "redis": "ok"}
```

If either service is down, `/ready` answers **503** with `"status": "not ready"` and the failing one marked `"unavailable"`. A load balancer should stop sending traffic to that instance until it recovers; do not restart the process on a readiness failure. The [Helm chart](/guides/deploying-with-helm) already points its probes at these paths.
