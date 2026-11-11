"""OpenTelemetry spans and SIEM export, as a sidecar that can never hurt a request.

Rules this module is built around (ARCHITECTURE_RULES.md sidecar pattern):
    * ``Telemetry.*`` never raises and never awaits: it only does a non-blocking ``put_nowait``
    * queues are bounded; when a collector is slow or down the oldest guarantee is the request path,
      so new items are dropped and counted instead of growing memory or blocking
    * sink and network errors are caught per batch, counted, and logged at most once a minute with
      the exception class only (messages can contain endpoints or credentials)
    * misconfiguration is the exception: it fails hard at startup, never silently turns export off

Spans follow the OpenTelemetry GenAI semantic conventions (``gen_ai.*``) and are sent as OTLP/HTTP
JSON, which needs no SDK. Prompts, completions and tool arguments are never attached.
"""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
import socket
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Generic, Protocol, TypeVar

import httpx

from app.config import settings
from app.services.security_events import (
    SecurityEvent,
    events_for_mcp_call,
    events_for_request,
    to_cef,
    to_json,
    to_syslog,
)

logger = logging.getLogger(__name__)
T = TypeVar("T")

SERVICE_VERSION = "1.0.0"
LOG_INTERVAL_SECONDS = 60.0
SIEM_FORMATS = ("json", "cef")
SIEM_SINKS = ("stdout", "file", "syslog_udp", "syslog_tcp")
SEND_TIMEOUT_SECONDS = 3.0

AttributeValue = str | int | float | bool

# ``gen_ai.operation.name``: the semantic-convention value where one exists (chat, embeddings), a descriptive one otherwise.
OPERATION_NAMES = {
    "chat": "chat", "embedding": "embeddings", "rerank": "rerank", "image": "image_generation",
    "transcription": "audio_transcription", "speech": "audio_speech", "responses": "responses",
}


# -- bounded background worker --------------------------------------------------------------------


class BoundedWorker(Generic[T]):
    """A queue plus one task that hands batches to ``handler``. ``submit`` never blocks or raises."""

    def __init__(
        self, name: str, handler: Callable[[list[T]], Awaitable[None]], *,
        max_queue: int, batch_size: int = 1, flush_interval: float = 0.0,
    ) -> None:
        self.name = name
        self._handler = handler
        self._queue: asyncio.Queue[T] = asyncio.Queue(maxsize=max_queue)
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._task: asyncio.Task | None = None
        self._last_log = 0.0
        self.submitted = self.dropped = self.sent = self.failed = 0

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.get_running_loop().create_task(self._run(), name=f"telemetry-{self.name}")

    async def stop(self, timeout: float = 5.0) -> None:
        if self._task is None:
            return
        try:
            await asyncio.wait_for(self._queue.join(), timeout)
        except (TimeoutError, asyncio.CancelledError):
            pass
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001 - shutdown must not raise
            pass
        self._task = None

    def submit(self, item: T) -> bool:
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            self.dropped += 1
            return False
        except Exception:  # noqa: BLE001 - a sidecar must never raise into a request
            self.dropped += 1
            return False
        self.submitted += 1
        return True

    async def _run(self) -> None:
        while True:
            batch = [await self._queue.get()]
            deadline = time.monotonic() + self._flush_interval
            while len(batch) < self._batch_size:
                try:
                    if self._flush_interval > 0:
                        batch.append(await asyncio.wait_for(self._queue.get(), max(deadline - time.monotonic(), 0.001)))
                    else:
                        batch.append(self._queue.get_nowait())
                except (TimeoutError, asyncio.QueueEmpty):
                    break
            try:
                await self._handler(batch)
                self.sent += len(batch)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - count and move on
                self.failed += len(batch)
                self._log_failure(exc)
            finally:
                for _ in batch:
                    self._queue.task_done()

    def _log_failure(self, exc: Exception) -> None:
        now = time.monotonic()
        if now - self._last_log >= LOG_INTERVAL_SECONDS:
            self._last_log = now
            logger.warning("telemetry %s export failing (%s); dropped=%d failed=%d", self.name, exc.__class__.__name__, self.dropped, self.failed)

    def stats(self) -> dict[str, int]:
        return {"submitted": self.submitted, "dropped": self.dropped, "sent": self.sent, "failed": self.failed}


# -- SIEM sinks -----------------------------------------------------------------------------------


class Sink(Protocol):
    async def send(self, lines: list[str]) -> None: ...
    async def close(self) -> None: ...


class StdoutSink:
    async def send(self, lines: list[str]) -> None:
        sys.stdout.write("".join(f"{line}\n" for line in lines))
        sys.stdout.flush()

    async def close(self) -> None:
        return None


class FileSink:
    def __init__(self, path: str) -> None:
        self._path = path

    async def send(self, lines: list[str]) -> None:
        payload = "".join(f"{line}\n" for line in lines)
        await asyncio.to_thread(self._append, payload)

    def _append(self, payload: str) -> None:
        with open(self._path, "a", encoding="utf-8") as handle:
            handle.write(payload)

    async def close(self) -> None:
        return None


class SyslogUdpSink:
    def __init__(self, host: str, port: int) -> None:
        self._addr = (host, port)
        self._sock: socket.socket | None = None

    async def send(self, lines: list[str]) -> None:
        if self._sock is None:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setblocking(False)
        loop = asyncio.get_running_loop()
        for line in lines:
            await asyncio.wait_for(loop.sock_sendto(self._sock, line.encode("utf-8"), self._addr), SEND_TIMEOUT_SECONDS)

    async def close(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None


class SyslogTcpSink:
    """Newline-framed RFC 5424 over TCP; reconnects after a failure. Bounded by SEND_TIMEOUT_SECONDS."""

    def __init__(self, host: str, port: int) -> None:
        self._host, self._port = host, port
        self._writer: asyncio.StreamWriter | None = None

    async def send(self, lines: list[str]) -> None:
        try:
            if self._writer is None or self._writer.is_closing():
                _, self._writer = await asyncio.wait_for(asyncio.open_connection(self._host, self._port), SEND_TIMEOUT_SECONDS)
            self._writer.write("".join(f"{line}\n" for line in lines).encode("utf-8"))
            await asyncio.wait_for(self._writer.drain(), SEND_TIMEOUT_SECONDS)
        except Exception:
            await self.close()
            raise

    async def close(self) -> None:
        writer, self._writer = self._writer, None
        if writer is not None:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), 1.0)
            except Exception:  # noqa: BLE001 - best effort
                pass


def build_sink(kind: str) -> Sink:
    if kind == "stdout":
        return StdoutSink()
    if kind == "file":
        if not settings.SIEM_FILE_PATH:
            raise ValueError("SIEM_SINK=file requires SIEM_FILE_PATH")
        return FileSink(settings.SIEM_FILE_PATH)
    if kind == "syslog_udp":
        return SyslogUdpSink(settings.SIEM_SYSLOG_HOST, settings.SIEM_SYSLOG_PORT)
    if kind == "syslog_tcp":
        return SyslogTcpSink(settings.SIEM_SYSLOG_HOST, settings.SIEM_SYSLOG_PORT)
    raise ValueError(f"SIEM_SINK must be one of {', '.join(SIEM_SINKS)}, got {kind!r}")


class SiemExporter:
    def __init__(self, fmt: str, sink: Sink, *, syslog_framing: bool, max_queue: int) -> None:
        if fmt not in SIEM_FORMATS:
            raise ValueError(f"SIEM_FORMAT must be one of {', '.join(SIEM_FORMATS)}, got {fmt!r}")
        self._format, self._sink, self._syslog = fmt, sink, syslog_framing
        self.worker: BoundedWorker[SecurityEvent] = BoundedWorker("siem", self._handle, max_queue=max_queue, batch_size=50)

    def render(self, event: SecurityEvent) -> str:
        body = to_cef(event) if self._format == "cef" else to_json(event)
        return to_syslog(event, body) if self._syslog else body

    async def _handle(self, events: list[SecurityEvent]) -> None:
        await self._sink.send([self.render(e) for e in events])

    def emit(self, event: SecurityEvent) -> None:
        self.worker.submit(event)

    async def close(self) -> None:
        await self._sink.close()


# -- OpenTelemetry spans (OTLP/HTTP JSON) ----------------------------------------------------------


@dataclass(frozen=True)
class Span:
    name: str
    start_ns: int
    end_ns: int
    attributes: dict[str, AttributeValue]
    kind: int = 3  # CLIENT
    error: str | None = None
    trace_id: str = field(default_factory=lambda: secrets.token_hex(16))
    span_id: str = field(default_factory=lambda: secrets.token_hex(8))


def _attr(key: str, value: AttributeValue) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    return {"key": key, "value": {"stringValue": str(value)}}


def otlp_payload(spans: list[Span], service_name: str) -> dict[str, Any]:
    return {"resourceSpans": [{
        "resource": {"attributes": [_attr("service.name", service_name), _attr("service.version", SERVICE_VERSION)]},
        "scopeSpans": [{"scope": {"name": "openproxyai", "version": SERVICE_VERSION}, "spans": [{
            "traceId": s.trace_id, "spanId": s.span_id, "name": s.name, "kind": s.kind,
            "startTimeUnixNano": str(s.start_ns), "endTimeUnixNano": str(s.end_ns),
            "attributes": [_attr(k, v) for k, v in s.attributes.items()],
            "status": {"code": 2, "message": s.error} if s.error else {"code": 1},
        } for s in spans]}],
    }]}


class OtlpSpanExporter:
    def __init__(self, endpoint: str, headers: dict[str, str], service_name: str, *, max_queue: int) -> None:
        self._url = endpoint.rstrip("/") + "/v1/traces"
        self._headers = {"Content-Type": "application/json", **headers}
        self._service = service_name
        self._client: httpx.AsyncClient | None = None
        self.worker: BoundedWorker[Span] = BoundedWorker("otlp", self._handle, max_queue=max_queue, batch_size=64, flush_interval=2.0)

    async def _handle(self, spans: list[Span]) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=5.0, follow_redirects=False)
        response = await self._client.post(self._url, json=otlp_payload(spans, self._service), headers=self._headers)
        response.raise_for_status()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def emit(self, span: Span) -> None:
        self.worker.submit(span)


def parse_headers(raw: str) -> dict[str, str]:
    """``k=v,k2=v2`` as in OTEL_EXPORTER_OTLP_HEADERS."""
    headers: dict[str, str] = {}
    for pair in filter(None, (p.strip() for p in raw.split(","))):
        key, sep, value = pair.partition("=")
        if not sep or not key.strip():
            raise ValueError("OTEL_EXPORTER_OTLP_HEADERS must look like key=value,key2=value2")
        headers[key.strip()] = value.strip()
    return headers


# -- facade ----------------------------------------------------------------------------------------


class Telemetry:
    """The only thing the rest of the code base touches. Every public method swallows its own errors."""

    def __init__(self) -> None:
        self.siem: SiemExporter | None = None
        self.otel: OtlpSpanExporter | None = None
        self.internal_errors = 0

    def configure_from_settings(self) -> None:
        """Build exporters from settings. Raises ValueError on bad config so startup fails hard."""
        self.siem = self.otel = None
        if settings.SIEM_EXPORT_ENABLED:
            kind = settings.SIEM_SINK
            self.siem = SiemExporter(
                settings.SIEM_FORMAT, build_sink(kind),
                syslog_framing=kind.startswith("syslog"), max_queue=settings.TELEMETRY_QUEUE_SIZE,
            )
        if settings.OTEL_EXPORT_ENABLED:
            if not settings.OTEL_EXPORTER_OTLP_ENDPOINT:
                raise ValueError("OTEL_EXPORT_ENABLED requires OTEL_EXPORTER_OTLP_ENDPOINT")
            self.otel = OtlpSpanExporter(
                settings.OTEL_EXPORTER_OTLP_ENDPOINT, parse_headers(settings.OTEL_EXPORTER_OTLP_HEADERS),
                settings.OTEL_SERVICE_NAME, max_queue=settings.TELEMETRY_QUEUE_SIZE,
            )

    def start(self) -> None:
        for exporter in (self.siem, self.otel):
            if exporter is not None:
                exporter.worker.start()

    async def stop(self) -> None:
        for exporter in (self.siem, self.otel):
            if exporter is None:
                continue
            await exporter.worker.stop()
            try:
                await exporter.close()
            except Exception:  # noqa: BLE001 - shutdown must not raise
                pass

    def stats(self) -> dict[str, Any]:
        return {
            "siem": self.siem.worker.stats() if self.siem else None,
            "otel": self.otel.worker.stats() if self.otel else None,
            "internal_errors": self.internal_errors,
        }

    # -- emit points (all non-blocking, none raise) ------------------------------------------------

    def event(self, event: SecurityEvent) -> None:
        try:
            if self.siem is not None:
                self.siem.emit(event)
        except Exception:  # noqa: BLE001
            self.internal_errors += 1

    def observe_request(
        self, *, request_id: Any, org_id: Any, user_id: Any, api_key_id: Any, model: str, provider: str,
        prompt_tokens: int, completion_tokens: int, cost_usd: float, latency_ms: int, status_code: int,
        error_message: str | None, policy_action: str | None = None, modality: str | None = None,
    ) -> None:
        """A finished request (chat, embeddings, rerank, images, audio, responses): security events plus one ``gen_ai`` span."""
        try:
            if self.siem is not None:
                for event in events_for_request(
                    status_code=status_code, error_message=error_message, model=model, provider=provider,
                    org_id=org_id, user_id=user_id, api_key_id=api_key_id, request_id=request_id,
                ):
                    self.siem.emit(event)
            if self.otel is not None:
                operation = OPERATION_NAMES.get(modality or "chat", "chat")
                attrs: dict[str, AttributeValue] = {
                    "gen_ai.operation.name": operation,
                    "gen_ai.system": provider or "unknown",
                    "gen_ai.request.model": model,
                    "gen_ai.usage.input_tokens": int(prompt_tokens or 0),
                    "gen_ai.usage.output_tokens": int(completion_tokens or 0),
                    "http.response.status_code": int(status_code),
                    "openproxyai.request_id": str(request_id),
                    "openproxyai.org_id": str(org_id),
                    "openproxyai.cost_usd": float(cost_usd or 0),
                }
                if policy_action:
                    attrs["openproxyai.policy.action"] = policy_action
                self.otel.emit(_span(f"{operation} {model}", latency_ms, attrs, status_code, _label(error_message, status_code)))
        except Exception:  # noqa: BLE001
            self.internal_errors += 1

    def observe_mcp_call(self, outcome: Any, *, org_id: Any, user_id: Any, api_key_id: Any, latency_ms: int) -> None:
        """A finished MCP tools/call: security events plus one ``execute_tool`` span."""
        try:
            request_id = secrets.token_hex(8)
            if self.siem is not None:
                for event in events_for_mcp_call(outcome, org_id=org_id, user_id=user_id, api_key_id=api_key_id, request_id=request_id):
                    self.siem.emit(event)
            if self.otel is not None:
                attrs: dict[str, AttributeValue] = {
                    "gen_ai.operation.name": "execute_tool",
                    "gen_ai.tool.name": str(outcome.tool),
                    "http.response.status_code": int(outcome.status_code),
                    "openproxyai.org_id": str(org_id),
                    "openproxyai.mcp.server": str(outcome.server or ""),
                }
                for key, value in (("pin_status", outcome.pin_status), ("scan_findings", ",".join(outcome.scan_findings))):
                    if value:
                        attrs[f"openproxyai.mcp.{key}"] = value
                reason = ((outcome.error or {}).get("data") or {}).get("reason_code")
                self.otel.emit(_span(f"execute_tool {outcome.tool}", latency_ms, attrs, outcome.status_code,
                                     _label(reason, outcome.status_code), kind=1))
        except Exception:  # noqa: BLE001
            self.internal_errors += 1


_LABEL = re.compile(r"[^A-Za-z0-9_.\- ]")


def _label(raw: str | None, status_code: int) -> str:
    """A short error label for a span: the part before the first colon, stripped of anything free-form."""
    head = _LABEL.sub("", (raw or "").split(":", 1)[0])[:60].strip()
    return head or f"HTTP {status_code}"


def _span(name: str, latency_ms: int, attrs: dict[str, AttributeValue], status_code: int,
          error_label: str | None, kind: int = 3) -> Span:
    end = time.time_ns()
    return Span(
        name=name, start_ns=end - max(int(latency_ms), 0) * 1_000_000, end_ns=end, attributes=attrs, kind=kind,
        error=error_label if status_code >= 400 else None,
    )


telemetry = Telemetry()
