"""Security events for SIEM export: what happened, to whom, why. Never what was said.

An event carries identifiers, reason codes and category names. It never carries prompts, completions,
tool arguments or tool results, so shipping events to a SIEM does not widen where customer data lives.

Formats:
    json    one JSON object per line
    cef     ArcSight Common Event Format (CEF:0), understood by Splunk, QRadar, Sentinel, Elastic
Both can be wrapped in an RFC 5424 syslog line for TCP/UDP collectors.
"""

from __future__ import annotations

import json
import re
import socket
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

VENDOR, PRODUCT = "OpenProxyAI", "Gateway"
FACILITY_LOCAL0 = 16

# event name -> (CEF severity 0-10, human description)
CATALOG: dict[str, tuple[int, str]] = {
    "AI-POLICY-BLOCK": (6, "Request blocked by organization policy"),
    "AI-DLP-BLOCK": (7, "Request or response blocked: sensitive data detected"),
    "AI-INJECTION-BLOCK": (8, "Prompt injection blocked"),
    "AI-INJECTION-FLAGGED": (5, "Possible prompt injection in tool output or description delivered"),
    "AI-UNAUTHORIZED-MCP": (7, "Unauthorized MCP gateway access attempt"),
    "AI-MCP-TOOL-BLOCK": (6, "MCP tool call blocked"),
    "AI-TOOL-DRIFT": (6, "MCP tool definition changed after approval"),
    "AI-TAINT-BLOCK": (8, "Side-effect tool blocked after untrusted content"),
    "AI-BUDGET-EXCEEDED": (5, "Budget exceeded"),
    "AI-RATE-LIMIT": (4, "Rate limit hit"),
}

DLP_REASONS = {"pii_detected", "response_pii_detected", "blocked_keyword", "response_keyword_blocked"}
INJECTION_REASONS = {"prompt_injection_detected", "tool_output_flagged"}
TAINT_REASONS = {"sink_blocked_tainted_session", "sink_requires_session", "tool_taint_forced_sink"}
_HOST = socket.gethostname()


@dataclass(frozen=True)
class SecurityEvent:
    name: str
    org_id: uuid.UUID | str | None = None
    user_id: uuid.UUID | str | None = None
    api_key_id: uuid.UUID | str | None = None
    request_id: uuid.UUID | str | None = None
    action: str = "block"  # block | flag
    reason: str | None = None
    # Small string fields only (model, tool, server, categories). Never user content.
    details: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def severity(self) -> int:
        return CATALOG[self.name][0]

    @property
    def description(self) -> str:
        return CATALOG[self.name][1]

    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "event": self.name,
            "severity": self.severity,
            "action": self.action,
            "reason": self.reason,
            "org_id": _s(self.org_id),
            "user_id": _s(self.user_id),
            "api_key_id": _s(self.api_key_id),
            "request_id": _s(self.request_id),
            "description": self.description,
            **{f"detail_{k}": v for k, v in self.details.items()},
        }


def _s(value: Any) -> str | None:
    return None if value is None else str(value)


# -- formats -------------------------------------------------------------------------------------


def to_json(event: SecurityEvent) -> str:
    return json.dumps(event.as_dict(), ensure_ascii=False, separators=(",", ":"))


def _cef_header(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _cef_ext(value: str) -> str:
    return value.replace("\\", "\\\\").replace("=", "\\=").replace("\r", "\\n").replace("\n", "\\n")


def to_cef(event: SecurityEvent, version: str = "1.0") -> str:
    ext: list[tuple[str, str]] = [("rt", str(int(event.timestamp.timestamp() * 1000))), ("act", event.action)]
    if event.reason:
        ext.append(("reason", event.reason))
    for key, value in (("externalId", event.request_id), ("suser", event.user_id)):
        if value is not None:
            ext.append((key, str(value)))
    custom = [("orgId", event.org_id), ("apiKeyId", event.api_key_id), *event.details.items()]
    for index, (label, value) in enumerate([(k, v) for k, v in custom if v is not None][:6], start=1):
        ext.append((f"cs{index}Label", label))
        ext.append((f"cs{index}", str(value)))
    header = "|".join(_cef_header(p) for p in ("CEF:0", VENDOR, PRODUCT, version, event.name, event.description, str(event.severity)))
    return header + "|" + " ".join(f"{k}={_cef_ext(v)}" for k, v in ext)


def _syslog_severity(cef: int) -> int:
    return 3 if cef >= 8 else 4 if cef >= 5 else 6  # error / warning / informational


def to_syslog(event: SecurityEvent, body: str, max_bytes: int = 2048) -> str:
    """RFC 5424: <PRI>1 TIMESTAMP HOSTNAME APP-NAME PROCID MSGID - MSG."""
    pri = FACILITY_LOCAL0 * 8 + _syslog_severity(event.severity)
    stamp = event.timestamp.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    line = f"<{pri}>1 {stamp} {_HOST} openproxyai - {event.name} - {body}"
    encoded = line.encode("utf-8")
    return line if len(encoded) <= max_bytes else encoded[:max_bytes].decode("utf-8", errors="ignore")


# -- deriving events from what the gateway already audits -----------------------------------------


_SAFE = re.compile(r"[^A-Za-z0-9_.:\-/ ]")


def _clean(value: Any, limit: int = 120) -> str:
    return _SAFE.sub("", str(value))[:limit]


def events_for_request(
    *, status_code: int, error_message: str | None, model: str, provider: str,
    org_id: Any, user_id: Any, api_key_id: Any, request_id: Any,
) -> list[SecurityEvent]:
    """Chat/embedding requests: policy blocks, DLP, injection, budget and rate limits."""
    base = {"org_id": org_id, "user_id": user_id, "api_key_id": api_key_id, "request_id": request_id}
    details = {"model": _clean(model), "provider": _clean(provider)}
    if status_code == 403 and error_message and error_message.startswith("policy_blocked:"):
        reason = _clean(error_message.split(":", 1)[1])
        name = ("AI-DLP-BLOCK" if reason in DLP_REASONS else "AI-INJECTION-BLOCK" if reason in INJECTION_REASONS
                else "AI-TAINT-BLOCK" if reason in TAINT_REASONS else "AI-POLICY-BLOCK")
        return [SecurityEvent(name, reason=reason, details=details, **base)]
    if status_code == 402:
        return [SecurityEvent("AI-BUDGET-EXCEEDED", reason="budget_exceeded", details=details, **base)]
    if status_code == 429:
        reason = _clean((error_message or "rate_limited").split(":", 1)[-1])
        return [SecurityEvent("AI-RATE-LIMIT", reason=reason, details=details, **base)]
    return []


def events_for_mcp_call(outcome: Any, *, org_id: Any, user_id: Any, api_key_id: Any, request_id: Any) -> list[SecurityEvent]:
    """MCP tools/call: blocks (policy, grants, bundle, pinning, taint, scanning), drift and flagged output."""
    base = {"org_id": org_id, "user_id": user_id, "api_key_id": api_key_id, "request_id": request_id}
    details = {"tool": _clean(outcome.tool), "server": _clean(outcome.server or "")}
    events: list[SecurityEvent] = []
    reason = ((outcome.error or {}).get("data") or {}).get("reason_code")
    if outcome.status_code == 446 and reason:
        reason = _clean(reason)
        if reason in TAINT_REASONS:
            name = "AI-TAINT-BLOCK"
        elif reason in INJECTION_REASONS:
            name = "AI-INJECTION-BLOCK"
        elif reason.startswith("tool_pin_"):
            name = "AI-TOOL-DRIFT" if reason == "tool_pin_drifted" else "AI-MCP-TOOL-BLOCK"
        elif reason in DLP_REASONS:
            name = "AI-DLP-BLOCK"
        else:
            name = "AI-MCP-TOOL-BLOCK"
        events.append(SecurityEvent(name, reason=reason, details=details, **base))
    elif outcome.status_code == 200 and outcome.pin_status == "drifted":
        events.append(SecurityEvent("AI-TOOL-DRIFT", action="flag", reason="tool_pin_drifted", details=details, **base))
    if outcome.scan_findings and outcome.status_code == 200:
        events.append(SecurityEvent(
            "AI-INJECTION-FLAGGED", action="flag", reason="tool_output_flagged",
            details={**details, "categories": ",".join(_clean(c, 40) for c in outcome.scan_findings)}, **base,
        ))
    return events
