---
title: Data Residency
description: Route requests only through provider keys in approved regions.
---

# Data Residency

Provider keys can be tagged with a `data_region`, and organizations can require that requests only ever route through keys in an approved set of regions.

## How it's enforced

Region filtering happens at the routing stage of the pipeline (see [Provider Routing](/core-concepts/provider-routing)) — before a request is sent to a provider, the router excludes any key outside the org's approved regions from the weighted-rotation candidate set entirely. This applies during failover too: a request never falls back to an out-of-region key, even if every in-region key is temporarily unhealthy.

## Configuring approved regions

Org-level data residency settings are managed alongside your organization's general configuration at `/api/v1/organizations/current`.

## Combining with compliance templates

The Government/FedRAMP-aligned [compliance template](/guides/compliance-templates) applies data residency enforcement as part of its defaults — apply it as a starting point rather than configuring region rules from scratch.
