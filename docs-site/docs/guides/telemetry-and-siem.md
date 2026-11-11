---
title: Telemetry and SIEM export
description: Send one OpenTelemetry span per request and security events to your SIEM, without any risk to the request path.
---

# Telemetry and SIEM export

Two optional exports, both **off by default**, both built so a slow or broken collector can never affect a request:

- **OpenTelemetry**: one `gen_ai` span per finished request (chat, embeddings, rerank, images, audio, Responses) and one per MCP tool call, as OTLP/HTTP JSON. No SDK is involved.
- **SIEM**: a security event for each block, budget stop or rate limit, as CEF or JSON, to stdout, a file, or syslog over UDP or TCP.

Prompts, completions and tool arguments are **never** attached to either.

## The rules they follow

| Rule | What it means |
|---|---|
| Never raises, never waits | Exporting is a non-blocking put on a bounded queue. A request does not know whether the export worked. |
| Bounded | At most `TELEMETRY_QUEUE_SIZE` items (default 2,000) per exporter. When a collector is slow or down, new items are **dropped and counted**, not queued without limit. |
| Quiet failures | Network errors are caught per batch, counted, and logged at most once a minute with the exception class only (messages can contain endpoints or credentials). |
| Bad configuration fails at startup | A missing endpoint or an unknown format stops the gateway from starting. It does not quietly turn export off. |

## OpenTelemetry

| Setting | |
|---|---|
| `OTEL_EXPORT_ENABLED` | `true` to turn on. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Your collector, for example `http://otel-collector:4318`. Required when enabled. |
| `OTEL_EXPORTER_OTLP_HEADERS` | `key=value,key2=value2`, for a collector that needs an auth header. |
| `OTEL_SERVICE_NAME` | Default `openproxyai`. |

Each span is named `<operation> <model>` and follows the GenAI semantic conventions:

| Attribute | |
|---|---|
| `gen_ai.operation.name` | `chat`, `embeddings`, `rerank`, `image_generation`, `audio_transcription`, `audio_speech`, `responses`, or `execute_tool` for an MCP call. |
| `gen_ai.system`, `gen_ai.request.model` | The provider and the model. |
| `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` | As the provider reported them (or estimated, for calls that report none). |
| `http.response.status_code` | The status the client got; an error status marks the span as an error. |
| `openproxyai.request_id`, `openproxyai.org_id`, `openproxyai.cost_usd` | To join a span to the request log and to spend. |
| `openproxyai.policy.action` | Set when policy acted on the request. |

## SIEM

| Setting | |
|---|---|
| `SIEM_EXPORT_ENABLED` | `true` to turn on. |
| `SIEM_FORMAT` | `cef` (default) or `json`. |
| `SIEM_SINK` | `stdout`, `file`, `syslog_udp` or `syslog_tcp`. |
| `SIEM_SYSLOG_HOST`, `SIEM_SYSLOG_PORT` | For the syslog sinks (default `127.0.0.1:514`). |
| `SIEM_FILE_PATH` | Required for the `file` sink. |

Events:

| Event | When |
|---|---|
| `AI-POLICY-BLOCK` | A request was refused by policy or by routing. |
| `AI-DLP-BLOCK` | Refused because of personal or sensitive data. |
| `AI-INJECTION-BLOCK`, `AI-INJECTION-FLAGGED` | Prompt injection detected (blocked, or flagged only). |
| `AI-TAINT-BLOCK` | A tool-using conversation that had handled untrusted tool output was stopped from using a sink tool. |
| `AI-BUDGET-EXCEEDED`, `AI-RATE-LIMIT` | A budget or rate limit stopped the request. |
| `AI-UNAUTHORIZED-MCP`, `AI-MCP-TOOL-BLOCK`, `AI-TOOL-DRIFT` | MCP gateway refusals and a tool whose definition changed after it was approved. |

Every event carries the organization, user, API key and request ids and the model or tool, never the content that triggered it.

## Try it locally

```bash
docker run -p 4318:4318 otel/opentelemetry-collector --config=... # or any OTLP/HTTP receiver
OTEL_EXPORT_ENABLED=true OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 \
SIEM_EXPORT_ENABLED=true SIEM_FORMAT=json SIEM_SINK=stdout \
uvicorn app.main:app
```
