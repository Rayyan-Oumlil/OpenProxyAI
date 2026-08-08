---
title: Deploying with Docker Compose
description: Run the full OpenProxyAI stack locally or on a single host with Docker Compose.
---

# Deploying with Docker Compose

The fastest way to run the full stack — proxy, Postgres, and Redis — on a single host.

## Prerequisites

- Docker and Docker Compose
- A `.env` file for the backend (copy `backend/.env.example` and fill in your values)

## Start the stack

```bash
docker compose up -d postgres redis
```

This starts Postgres (with the `pgvector` extension enabled, required for semantic caching) and Redis. The `postgres` container publishes to the host on a non-default port to avoid clashing with a local Postgres install — check your `docker-compose.yml` for the exact mapping.

## Run migrations

```bash
docker compose exec backend alembic upgrade head
```

Or, if running the backend outside Docker against the containerized database, point `DATABASE_URL` at the host-mapped port rather than the in-network service name — the two are not interchangeable.

## Start the API

```bash
uvicorn app.main:app --reload --port 8000
```

Or run it as its own Compose service if your `docker-compose.yml` defines an `api` service — check whether it requires a GPU reservation before running it that way; not every host has one configured.

## Verify it's running

```bash
curl http://localhost:8000/health
```

A `200` response with the app's startup log showing "Startup complete" confirms the database and Redis connections succeeded.

## Optional sidecars

ClickHouse (analytics dual-write) sits behind a Compose profile and is not started by default:

```bash
docker compose --profile analytics up -d clickhouse
```

It's a sidecar — the proxy runs normally without it. See [Environment Flags](/getting-started/environment-flags).
