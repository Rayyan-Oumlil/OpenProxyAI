"""Telemetry sidecar: bounded queues, failing sinks, OTLP payloads, config validation, never-raise facade."""

import asyncio
import json
import socket
import uuid

import httpx
import pytest

from app.config import settings
from app.services import telemetry as tm
from app.services.mcp_gateway import ToolCallOutcome
from app.services.security_events import SecurityEvent
from app.services.telemetry import BoundedWorker, SiemExporter, Telemetry

EVENT = SecurityEvent("AI-POLICY-BLOCK", org_id=uuid.uuid4(), reason="blocked_keyword")


# -- worker --------------------------------------------------------------------------------------


async def test_worker_delivers_in_batches_and_drains_on_stop():
	seen: list[list[int]] = []

	async def handler(batch):
		seen.append(batch)

	worker = BoundedWorker("t", handler, max_queue=100, batch_size=10)
	worker.start()
	for i in range(25):
		assert worker.submit(i)
	await worker.stop()
	assert sorted(i for batch in seen for i in batch) == list(range(25)) and worker.sent == 25 and worker.dropped == 0


async def test_a_full_queue_drops_and_counts_without_blocking_or_raising():
	gate = asyncio.Event()

	async def stuck(batch):
		await gate.wait()

	worker = BoundedWorker("t", stuck, max_queue=3, batch_size=1)
	worker.start()
	await asyncio.sleep(0.01)
	results = [worker.submit(i) for i in range(50)]  # returns immediately every time
	assert results.count(False) >= 45 and worker.dropped == results.count(False)
	gate.set()
	await worker.stop()


async def test_handler_failures_are_counted_and_the_worker_keeps_going():
	calls = []

	async def flaky(batch):
		calls.append(batch)
		if batch == [1]:
			raise RuntimeError("collector is down")

	worker = BoundedWorker("t", flaky, max_queue=10, batch_size=1)
	worker.start()
	for i in range(3):
		worker.submit(i)
	await worker.stop()
	assert worker.failed == 1 and worker.sent == 2 and len(calls) == 3


async def test_failure_logging_is_rate_limited_and_hides_exception_text(caplog):
	async def boom(batch):
		raise RuntimeError("secret-token-in-url")

	worker = BoundedWorker("t", boom, max_queue=100, batch_size=1)
	worker.start()
	with caplog.at_level("WARNING", logger="app.services.telemetry"):
		for i in range(20):
			worker.submit(i)
		await worker.stop()
	assert len([r for r in caplog.records if "export failing" in r.message]) == 1
	assert "secret-token-in-url" not in caplog.text and "RuntimeError" in caplog.text


# -- SIEM sinks ----------------------------------------------------------------------------------


class MemorySink:
	def __init__(self, fail=False):
		self.lines, self.fail, self.closed = [], fail, False

	async def send(self, lines):
		if self.fail:
			raise ConnectionError("down")
		self.lines += lines

	async def close(self):
		self.closed = True


async def test_siem_exporter_renders_the_configured_format_and_framing():
	cef, jsn, sys_cef = MemorySink(), MemorySink(), MemorySink()
	for fmt, sink, framed in (("cef", cef, False), ("json", jsn, False), ("cef", sys_cef, True)):
		exporter = SiemExporter(fmt, sink, syslog_framing=framed, max_queue=10)
		exporter.worker.start()
		exporter.emit(EVENT)
		await exporter.worker.stop()
	assert cef.lines[0].startswith("CEF:0|OpenProxyAI|") and json.loads(jsn.lines[0])["event"] == "AI-POLICY-BLOCK"
	assert sys_cef.lines[0].startswith("<132>1 ") and " AI-POLICY-BLOCK - CEF:0|" in sys_cef.lines[0]


async def test_file_sink_appends_lines(tmp_path):
	path = tmp_path / "siem.log"
	sink = tm.FileSink(str(path))
	await sink.send(["one", "two"])
	await sink.send(["three"])
	assert path.read_text(encoding="utf-8").splitlines() == ["one", "two", "three"]


async def test_udp_sink_delivers_datagrams():
	receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	receiver.bind(("127.0.0.1", 0))
	receiver.settimeout(2)
	sink = tm.SyslogUdpSink("127.0.0.1", receiver.getsockname()[1])
	await sink.send(["<14>1 hello"])
	assert receiver.recvfrom(4096)[0] == b"<14>1 hello"
	await sink.close()
	receiver.close()


async def test_tcp_sink_delivers_and_reconnects_after_the_collector_restarts():
	received: list[bytes] = []

	async def serve(reader, writer):
		received.append(await reader.readline())
		writer.close()

	server = await asyncio.start_server(serve, "127.0.0.1", 0)
	port = server.sockets[0].getsockname()[1]
	sink = tm.SyslogTcpSink("127.0.0.1", port)
	await sink.send(["first"])
	await asyncio.sleep(0.1)  # the server closed this connection
	for attempt in range(3):  # a write on the dead connection may need one failed attempt before reconnecting
		try:
			await sink.send(["second"])
			await asyncio.sleep(0.1)
			if len(received) >= 2:
				break
		except Exception:
			continue
	assert received[0] == b"first\n" and b"second\n" in received
	await sink.close()
	server.close()
	await server.wait_closed()


async def test_tcp_sink_to_a_dead_collector_raises_quickly_instead_of_hanging():
	with socket.socket() as probe:
		probe.bind(("127.0.0.1", 0))
		port = probe.getsockname()[1]
	sink = tm.SyslogTcpSink("127.0.0.1", port)
	with pytest.raises(OSError):
		await asyncio.wait_for(sink.send(["x"]), 5)


async def test_a_failing_sink_never_blocks_emit_and_counts_failures():
	exporter = SiemExporter("json", MemorySink(fail=True), syslog_framing=False, max_queue=5)
	exporter.worker.start()
	for _ in range(100):
		exporter.emit(EVENT)  # synchronous and instant
	await exporter.worker.stop()
	assert exporter.worker.failed > 0 and exporter.worker.dropped > 0


# -- OTLP ----------------------------------------------------------------------------------------


def test_otlp_payload_shape_and_attribute_types():
	span = tm.Span("chat gpt", 1_000, 2_000, {"s": "x", "i": 3, "f": 1.5, "b": True}, error="policy_blocked")
	payload = tm.otlp_payload([span], "svc")
	resource = payload["resourceSpans"][0]
	assert {"key": "service.name", "value": {"stringValue": "svc"}} in resource["resource"]["attributes"]
	[out] = resource["scopeSpans"][0]["spans"]
	assert len(out["traceId"]) == 32 and len(out["spanId"]) == 16 and out["startTimeUnixNano"] == "1000"
	attrs = {a["key"]: a["value"] for a in out["attributes"]}
	assert attrs == {"s": {"stringValue": "x"}, "i": {"intValue": "3"}, "f": {"doubleValue": 1.5}, "b": {"boolValue": True}}
	assert out["status"] == {"code": 2, "message": "policy_blocked"}
	assert tm.otlp_payload([tm.Span("ok", 1, 2, {})], "s")["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["status"] == {"code": 1}


def test_parse_headers():
	assert tm.parse_headers("a=1, b = two=2 ") == {"a": "1", "b": "two=2"} and tm.parse_headers("") == {}
	for bad in ("novalue", "=x"):
		with pytest.raises(ValueError):
			tm.parse_headers(bad)


async def test_otlp_exporter_posts_batched_json_with_headers():
	seen: list[httpx.Request] = []

	def handler(request: httpx.Request) -> httpx.Response:
		seen.append(request)
		return httpx.Response(200, json={})

	exporter = tm.OtlpSpanExporter("http://collector:4318/", {"x-api-key": "k"}, "svc", max_queue=100)
	exporter._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
	exporter.worker.start()
	for i in range(5):
		exporter.emit(tm.Span(f"chat {i}", 1, 2, {"gen_ai.operation.name": "chat"}))
	await exporter.worker.stop()
	await exporter.close()
	assert len(seen) >= 1 and str(seen[0].url) == "http://collector:4318/v1/traces" and seen[0].headers["x-api-key"] == "k"
	names = [s["name"] for r in seen for s in json.loads(r.content)["resourceSpans"][0]["scopeSpans"][0]["spans"]]
	assert sorted(names) == [f"chat {i}" for i in range(5)]


@pytest.mark.parametrize("failure", ["status", "connect"])
async def test_otlp_failures_are_counted_not_raised(failure):
	def handler(request):
		if failure == "connect":
			raise httpx.ConnectError("refused")
		return httpx.Response(503)

	exporter = tm.OtlpSpanExporter("http://collector:4318", {}, "svc", max_queue=10)
	exporter._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
	exporter.worker.start()
	exporter.emit(tm.Span("chat", 1, 2, {}))
	await exporter.worker.stop()
	assert exporter.worker.failed == 1 and exporter.worker.sent == 0


# -- facade --------------------------------------------------------------------------------------


class Recorder:
	def __init__(self):
		self.items = []

	def emit(self, item):
		self.items.append(item)


class Exploding:
	def emit(self, item):
		raise RuntimeError("exporter bug")


REQUEST = dict(
	request_id=uuid.uuid4(), org_id=uuid.uuid4(), user_id=uuid.uuid4(), api_key_id=uuid.uuid4(), model="openai/gpt-4o",
	provider="openai", prompt_tokens=12, completion_tokens=7, cost_usd=0.002, latency_ms=250, status_code=200, error_message=None,
)


def test_request_span_follows_the_gen_ai_conventions_and_carries_no_content():
	telemetry = Telemetry()
	telemetry.otel = Recorder()
	telemetry.observe_request(**REQUEST)
	[span] = telemetry.otel.items
	assert span.name == "chat openai/gpt-4o" and span.error is None
	assert span.end_ns - span.start_ns == 250 * 1_000_000
	assert span.attributes["gen_ai.operation.name"] == "chat" and span.attributes["gen_ai.system"] == "openai"
	assert span.attributes["gen_ai.request.model"] == "openai/gpt-4o"
	assert span.attributes["gen_ai.usage.input_tokens"] == 12 and span.attributes["gen_ai.usage.output_tokens"] == 7
	assert not any(k.startswith("gen_ai.prompt") or k.startswith("gen_ai.completion") for k in span.attributes)


def test_failed_requests_mark_the_span_with_a_sanitised_label():
	telemetry = Telemetry()
	telemetry.otel = Recorder()
	telemetry.observe_request(**{**REQUEST, "status_code": 502, "error_message": "Connection error to https://x.example/?key=SECRET: boom"})
	[span] = telemetry.otel.items
	assert span.error == "Connection error to https" and "SECRET" not in span.error


def test_blocked_request_emits_a_siem_event_and_an_error_span():
	telemetry = Telemetry()
	telemetry.siem, telemetry.otel = Recorder(), Recorder()
	telemetry.observe_request(**{**REQUEST, "status_code": 446, "error_message": "policy_blocked:pii_detected", "policy_action": "block"})
	assert [e.name for e in telemetry.siem.items] == ["AI-DLP-BLOCK"]
	assert telemetry.otel.items[0].error == "policy_blocked" and telemetry.otel.items[0].attributes["openproxyai.policy.action"] == "block"


def test_mcp_calls_emit_tool_spans_and_events():
	telemetry = Telemetry()
	telemetry.siem, telemetry.otel = Recorder(), Recorder()
	outcome = ToolCallOutcome(tool="mail__send", server="mail", status_code=446, decision=None, pin_status="approved",
	                          error={"code": -32009, "message": "text", "data": {"reason_code": "sink_requires_session"}})
	telemetry.observe_mcp_call(outcome, org_id=uuid.uuid4(), user_id=uuid.uuid4(), api_key_id=uuid.uuid4(), latency_ms=5)
	assert [e.name for e in telemetry.siem.items] == ["AI-TAINT-BLOCK"]
	[span] = telemetry.otel.items
	assert span.name == "execute_tool mail__send" and span.attributes["gen_ai.tool.name"] == "mail__send"
	assert span.error == "sink_requires_session" and span.attributes["openproxyai.mcp.pin_status"] == "approved"


def test_the_facade_never_raises_whatever_the_exporters_do():
	telemetry = Telemetry()
	telemetry.siem, telemetry.otel = Exploding(), Exploding()
	telemetry.event(EVENT)
	telemetry.observe_request(**{**REQUEST, "status_code": 446, "error_message": "policy_blocked:pii_detected"})
	telemetry.observe_mcp_call(ToolCallOutcome(tool="t", server="s", status_code=200, decision=None),
	                           org_id=1, user_id=2, api_key_id=3, latency_ms=1)
	telemetry.observe_request(**{**REQUEST, "latency_ms": "not-a-number", "cost_usd": object()})  # malformed values are swallowed too
	assert telemetry.internal_errors >= 4


def test_disabled_telemetry_is_a_no_op():
	telemetry = Telemetry()
	telemetry.event(EVENT)
	telemetry.observe_request(**REQUEST)
	assert telemetry.stats() == {"siem": None, "otel": None, "internal_errors": 0}


# -- configuration (fail hard at startup) --------------------------------------------------------


def configure(monkeypatch, **overrides):
	defaults = dict(SIEM_EXPORT_ENABLED=False, OTEL_EXPORT_ENABLED=False, SIEM_FORMAT="cef", SIEM_SINK="stdout", SIEM_FILE_PATH="",
	                OTEL_EXPORTER_OTLP_ENDPOINT="", OTEL_EXPORTER_OTLP_HEADERS="", TELEMETRY_QUEUE_SIZE=10)
	for key, value in {**defaults, **overrides}.items():
		monkeypatch.setattr(settings, key, value)
	telemetry = Telemetry()
	telemetry.configure_from_settings()
	return telemetry


def test_nothing_is_configured_by_default(monkeypatch):
	telemetry = configure(monkeypatch)
	assert telemetry.siem is None and telemetry.otel is None


def test_valid_configuration_builds_exporters(monkeypatch, tmp_path):
	telemetry = configure(monkeypatch, SIEM_EXPORT_ENABLED=True, SIEM_SINK="file", SIEM_FILE_PATH=str(tmp_path / "x"),
	                      OTEL_EXPORT_ENABLED=True, OTEL_EXPORTER_OTLP_ENDPOINT="http://c:4318", OTEL_EXPORTER_OTLP_HEADERS="a=b")
	assert telemetry.siem is not None and telemetry.otel is not None


@pytest.mark.parametrize("overrides", [
	{"SIEM_EXPORT_ENABLED": True, "SIEM_FORMAT": "xml"},
	{"SIEM_EXPORT_ENABLED": True, "SIEM_SINK": "carrier-pigeon"},
	{"SIEM_EXPORT_ENABLED": True, "SIEM_SINK": "file", "SIEM_FILE_PATH": ""},
	{"OTEL_EXPORT_ENABLED": True, "OTEL_EXPORTER_OTLP_ENDPOINT": ""},
	{"OTEL_EXPORT_ENABLED": True, "OTEL_EXPORTER_OTLP_ENDPOINT": "http://c", "OTEL_EXPORTER_OTLP_HEADERS": "broken"},
])
def test_bad_configuration_fails_hard_instead_of_silently_disabling_export(monkeypatch, overrides):
	with pytest.raises(ValueError):
		configure(monkeypatch, **overrides)


@pytest.mark.parametrize("modality,operation", [
	(None, "chat"), ("embedding", "embeddings"), ("rerank", "rerank"), ("image", "image_generation"),
	("transcription", "audio_transcription"), ("speech", "audio_speech"), ("responses", "responses"), ("something-new", "chat"),
])
def test_a_span_is_named_for_what_the_call_was_not_always_chat(modality, operation):
	telemetry = Telemetry()
	telemetry.otel = Recorder()
	telemetry.observe_request(**{**REQUEST, "modality": modality})
	[span] = telemetry.otel.items
	assert span.attributes["gen_ai.operation.name"] == operation and span.name.startswith(f"{operation} ")
