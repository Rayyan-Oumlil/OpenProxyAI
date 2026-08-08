---
title: Deploying with Helm
description: Run OpenProxyAI on Kubernetes for production and air-gapped deployments.
---

# Deploying with Helm

For production and air-gapped deployments, OpenProxyAI ships a Helm chart under `deploy/` in the repository.

```bash
helm install openproxyai ./deploy/helm \
  --namespace openproxyai --create-namespace \
  -f my-values.yaml
```

## What the chart deploys

The chart deploys the proxy API as a Kubernetes `Deployment`, along with the supporting services (or connects to externally-managed equivalents, depending on your values file) for Postgres and Redis.

## Air-gapped deployments

Set `AIRGAP_MODE=true` in your values overrides to disable everything that isn't required for the core request path — see [Environment Flags](/getting-started/environment-flags). This is the recommended configuration for the Government/FedRAMP-aligned deployment pattern; see [FedRAMP-aligned template](/security/fedramp-template).

## CI/CD

The repository's GitHub Actions workflows build and publish container images used by this chart. If you're customizing the deployment pipeline, start from `deploy/` in the repo rather than the default values file alone.

:::info Full values.yaml reference coming soon
This page covers the deployment model. A complete field-by-field `values.yaml` reference is planned — until then, treat the chart's own `values.yaml` and its inline comments as the source of truth for available options.
:::
