"""SIEM event formats (CEF, JSON, RFC 5424) and how events are derived from what the gateway audits."""

import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.services.mcp_gateway import ToolCallOutcome
from app.services.security_events import (
	CATALOG,
	SecurityEvent,
	events_for_mcp_call,
	events_for_request,
	to_cef,
	to_json,
	to_syslog,
)

ORG, USER, KEY, REQ = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
WHEN = datetime(2026, 11, 3, 12, 30, 45, 123000, tzinfo=UTC)


def event(name="AI-POLICY-BLOCK", **kw) -> SecurityEvent:
	return SecurityEvent(name, org_id=ORG, user_id=USER, api_key_id=KEY, request_id=REQ, timestamp=WHEN, **kw)


# -- formats -------------------------------------------------------------------------------------


def test_json_is_one_line_with_ids_and_no_free_text():
	line = to_json(event(reason="blocked_keyword", details={"model": "openai/gpt-4o"}))
	data = json.loads(line)
	assert "\n" not in line
	assert data["event"] == "AI-POLICY-BLOCK" and data["severity"] == 6 and data["reason"] == "blocked_keyword"
	assert data["org_id"] == str(ORG) and data["detail_model"] == "openai/gpt-4o" and data["timestamp"].startswith("2026-11-03T12:30:45")


def test_cef_header_and_extension_layout():
	cef = to_cef(event(reason="pii_detected", details={"model": "m"}))
	header = cef.split("|")
	assert header[:7] == ["CEF:0", "OpenProxyAI", "Gateway", "1.0", "AI-POLICY-BLOCK", "Request blocked by organization policy", "6"]
	extension = cef.split("|", 7)[7]
	assert "rt=1793709045123" in extension and "act=block" in extension and "reason=pii_detected" in extension
	assert f"externalId={REQ}" in extension and f"suser={USER}" in extension
	assert "cs1Label=orgId" in extension and f"cs1={ORG}" in extension and "cs3Label=model" in extension


def test_cef_escapes_header_and_extension_metacharacters():
	nasty = event(reason="a=b|c\\d\nnext", details={"tool": "x=y"})
	cef = to_cef(nasty)
	assert cef.count("\n") == 0
	assert "reason=a\\=b|c\\\\d\\nnext" in cef  # '=' and backslash escaped, newline folded, '|' is legal in extensions
	assert "cs3=x\\=y" in cef
	header = to_cef(SecurityEvent("AI-RATE-LIMIT")).split("|")
	assert len(header) >= 8  # a name containing '|' would shift this; catalog names never do


def test_syslog_wraps_with_rfc5424_header_and_severity_mapping():
	line = to_syslog(event("AI-INJECTION-BLOCK"), "BODY")
	assert line.startswith("<131>1 2026-11-03T12:30:45.123Z ") and line.endswith(" openproxyai - AI-INJECTION-BLOCK - BODY")
	assert to_syslog(event("AI-POLICY-BLOCK"), "x").startswith("<132>1 ")  # warning
	assert to_syslog(event("AI-RATE-LIMIT"), "x").startswith("<134>1 ")  # informational


def test_syslog_truncates_long_messages_on_a_character_boundary():
	line = to_syslog(event(), "é" * 5000, max_bytes=512)
	assert len(line.encode("utf-8")) <= 512 and line.encode("utf-8").decode("utf-8") == line


def test_every_catalog_event_renders_in_every_format():
	for name in CATALOG:
		ev = SecurityEvent(name, org_id=ORG)
		assert to_cef(ev).startswith("CEF:0|") and json.loads(to_json(ev))["event"] == name and to_syslog(ev, "b").startswith("<")


# -- deriving events -----------------------------------------------------------------------------


def ids():
	return {"org_id": ORG, "user_id": USER, "api_key_id": KEY, "request_id": REQ}


def derive(status, error=None, model="openai/gpt-4o"):
	return events_for_request(status_code=status, error_message=error, model=model, provider="openai", **ids())


@pytest.mark.parametrize(("error", "expected"), [
	("policy_blocked:pii_detected", "AI-DLP-BLOCK"),
	("policy_blocked:response_pii_detected", "AI-DLP-BLOCK"),
	("policy_blocked:blocked_keyword", "AI-DLP-BLOCK"),
	("policy_blocked:prompt_injection_detected", "AI-INJECTION-BLOCK"),
	("policy_blocked:tool_taint_forced_sink", "AI-TAINT-BLOCK"),
	("policy_blocked:model_not_allowed", "AI-POLICY-BLOCK"),
])
def test_policy_blocks_map_to_the_right_event(error, expected):
	[ev] = derive(403, error)
	assert ev.name == expected and ev.reason == error.split(":")[1] and ev.details["model"] == "openai/gpt-4o"


def test_budget_and_rate_limit_events():
	assert derive(402)[0].name == "AI-BUDGET-EXCEEDED"
	[limited] = derive(429, "rate_limited:rpm")
	assert limited.name == "AI-RATE-LIMIT" and limited.reason == "rpm"


@pytest.mark.parametrize("status", [200, 201, 400, 404, 500, 502])
def test_ordinary_outcomes_produce_no_events(status):
	assert derive(status, "upstream failed") == []


def test_a_403_that_is_not_a_policy_block_produces_nothing():
	assert derive(403, "forbidden") == []


def test_user_controlled_text_is_stripped_from_details():
	[ev] = derive(403, "policy_blocked:x", model="evil\n<script>alert(1)</script>|=")
	assert all(c not in ev.details["model"] for c in "<>|=\n")


def outcome(**kw):
	defaults = dict(tool="github__search", server="github", status_code=200, decision=None, scan_findings=(), pin_status=None, error=None)
	return ToolCallOutcome(**{**defaults, **kw})


def mcp(**kw):
	return events_for_mcp_call(outcome(**kw), **ids())


@pytest.mark.parametrize(("reason", "expected"), [
	("tool_blocked", "AI-MCP-TOOL-BLOCK"), ("tool_not_granted", "AI-MCP-TOOL-BLOCK"), ("tool_not_in_bundle", "AI-MCP-TOOL-BLOCK"),
	("tool_pin_pending", "AI-MCP-TOOL-BLOCK"), ("tool_pin_drifted", "AI-TOOL-DRIFT"),
	("sink_blocked_tainted_session", "AI-TAINT-BLOCK"), ("sink_requires_session", "AI-TAINT-BLOCK"),
	("tool_output_flagged", "AI-INJECTION-BLOCK"), ("pii_detected", "AI-DLP-BLOCK"),
])
def test_blocked_mcp_calls_map_to_the_right_event(reason, expected):
	[ev] = mcp(status_code=446, error={"code": -32001, "message": "secret detail", "data": {"reason_code": reason}})
	assert ev.name == expected and ev.reason == reason and ev.details == {"tool": "github__search", "server": "github"}
	assert "secret detail" not in to_json(ev) + to_cef(ev)


def test_delivered_but_flagged_output_and_drifted_tools_are_flagged_not_blocked():
	events = mcp(scan_findings=("markdown_exfil", "unicode_tag"), pin_status="drifted")
	assert [(e.name, e.action) for e in events] == [("AI-TOOL-DRIFT", "flag"), ("AI-INJECTION-FLAGGED", "flag")]
	assert events[1].details["categories"] == "markdown_exfil,unicode_tag"


def test_clean_successful_mcp_calls_produce_nothing():
	assert mcp() == [] and mcp(pin_status="approved") == []


def test_blocked_scan_does_not_double_report_as_flagged():
	events = mcp(status_code=446, scan_findings=("markdown_exfil",), error={"code": -32007, "message": "x", "data": {"reason_code": "tool_output_flagged"}})
	assert [e.name for e in events] == ["AI-INJECTION-BLOCK"]


def test_events_never_contain_tool_arguments_or_results():
	result = SimpleNamespace(result={"content": [{"text": "SECRET-RESULT"}]})  # not part of the event model at all
	assert "SECRET-RESULT" not in to_json(mcp(scan_findings=("x",))[0]) and result
