"""Taint tracking and session binding for agent tool use (design-specs A.7).

The attack: an agent reads untrusted content (a web page, an email, a ticket) through one tool, the
content tells the model to call a tool with side effects (send, write, delete), and the agent obeys.
Scanning (PR 4) catches known phrasing; taint tracking is the structural defence:

    * every tool result from a tool not marked ``trusted_output`` taints the MCP *session*;
    * a tool marked ``sink`` refuses to run in a tainted session, or without a session at all
      (a client that drops the session id must not be able to launder the taint away).

The same rule protects plain chat completions: when the conversation contains a tool message from an
untrusted tool, sink tools are removed from the request's ``tools`` before the model sees them.

Sessions live in Redis (``mcp:sess:<id>``, a hash) and are bound to the API key that initialised them:
another key presenting the id gets the same answer as for an unknown id.
"""

from __future__ import annotations

import fnmatch
import re
import secrets
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_trust_rule import ToolTrustRule

RULES = ("trusted_output", "sink")
SESSION_TTL_SECONDS = 3600
SESSION_ID_RE = re.compile(r"^[0-9a-f]{32}$")

REASON_SINK_TAINTED = "sink_blocked_tainted_session"
REASON_SINK_NO_SESSION = "sink_requires_session"
REASON_FORCED_SINK = "tool_taint_forced_sink"


def _matches(name: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


@dataclass(frozen=True)
class TrustRules:
    trusted_output: tuple[str, ...] = ()
    sinks: tuple[str, ...] = ()

    def output_untrusted(self, tool_name: str) -> bool:
        return not _matches(tool_name, self.trusted_output)

    def is_sink(self, tool_name: str) -> bool:
        return _matches(tool_name, self.sinks)

    @property
    def has_sinks(self) -> bool:
        return bool(self.sinks)


async def load_trust_rules(db: AsyncSession, org_id: uuid.UUID) -> TrustRules:
    rows = await db.execute(select(ToolTrustRule.rule, ToolTrustRule.tool_pattern).where(ToolTrustRule.org_id == org_id))
    found = rows.all()
    return TrustRules(
        trusted_output=tuple(sorted(p for r, p in found if r == "trusted_output")),
        sinks=tuple(sorted(p for r, p in found if r == "sink")),
    )


# -- MCP sessions -------------------------------------------------------------------------------


@dataclass(frozen=True)
class SessionState:
    session_id: str
    tainted: bool


@dataclass(frozen=True)
class TaintContext:
    """What call_tool needs to decide about a sink: the org's rules and the caller's session (None = no session)."""

    rules: TrustRules
    session: SessionState | None

    @property
    def label(self) -> str:
        if self.session is None:
            return "none"
        return "tainted" if self.session.tainted else "clean"


def _key(session_id: str) -> str:
    return f"mcp:sess:{session_id}"


async def create_session(redis: Redis, api_key_id: uuid.UUID) -> str:
    session_id = secrets.token_hex(16)
    await redis.hset(_key(session_id), mapping={"api_key_id": str(api_key_id), "tainted": "0"})
    await redis.expire(_key(session_id), SESSION_TTL_SECONDS)
    return session_id


async def get_session(redis: Redis, session_id: str, api_key_id: uuid.UUID) -> SessionState | None:
    """The session if it exists and belongs to ``api_key_id``; otherwise None (unknown looks the same as foreign)."""
    if not SESSION_ID_RE.fullmatch(session_id):
        return None
    data = await redis.hgetall(_key(session_id))
    if not data or _text(data.get("api_key_id")) != str(api_key_id):
        return None
    await redis.expire(_key(session_id), SESSION_TTL_SECONDS)
    return SessionState(session_id=session_id, tainted=_text(data.get("tainted")) == "1")


async def mark_tainted(redis: Redis, session_id: str) -> None:
    await redis.hset(_key(session_id), mapping={"tainted": "1"})


def _text(value: Any) -> str | None:
    return value.decode() if isinstance(value, bytes) else value


# -- chat completions ---------------------------------------------------------------------------


def conversation_is_tainted(messages: Iterable[Any], rules: TrustRules) -> bool:
    """True if any ``role=tool`` message came from a tool that is not trusted (or from an unknown tool)."""
    messages = list(messages)
    call_names: dict[str, str] = {}
    for message in messages:
        for call in (message.model_extra or {}).get("tool_calls") or []:
            if isinstance(call, dict) and isinstance(call.get("id"), str):
                name = (call.get("function") or {}).get("name")
                if isinstance(name, str):
                    call_names[call["id"]] = name
    for message in messages:
        if message.role != "tool":
            continue
        extra = message.model_extra or {}
        name = call_names.get(extra.get("tool_call_id")) or extra.get("name")
        if not isinstance(name, str) or rules.output_untrusted(name):
            return True
    return False


@dataclass(frozen=True)
class ChatTaintResult:
    request: Any  # the request to send on (a restricted copy when sinks were removed)
    tainted: bool = False
    removed: tuple[str, ...] = ()
    forced_sink: str | None = None  # tool_choice demanded a sink in a tainted conversation


def _tool_name(entry: Any) -> str | None:
    if isinstance(entry, dict):
        function = entry.get("function")
        name = function.get("name") if isinstance(function, dict) else entry.get("name")
        return name if isinstance(name, str) else None
    return None


def restrict_chat_request(request: Any, rules: TrustRules, *, enforce: bool) -> ChatTaintResult:
    """Remove sink tools from a tainted conversation's request. ``enforce=False`` only reports."""
    if not rules.has_sinks or not conversation_is_tainted(request.messages, rules):
        return ChatTaintResult(request=request)

    extra = dict(request.model_extra or {})
    removed: list[str] = []
    for key in ("tools", "functions"):
        entries = extra.get(key)
        if not isinstance(entries, list):
            continue
        kept = []
        for entry in entries:
            name = _tool_name(entry)
            if name and rules.is_sink(name):
                removed.append(name)
            else:
                kept.append(entry)
        extra[key] = kept
    forced = None
    for key in ("tool_choice", "function_call"):
        name = _tool_name(extra.get(key)) if isinstance(extra.get(key), dict) else None
        if name and rules.is_sink(name):
            forced = name

    if not enforce:
        return ChatTaintResult(request=request, tainted=True, removed=tuple(sorted(set(removed))), forced_sink=forced)

    # An empty tools list is rejected by providers, and tool_choice without tools is meaningless.
    for key, choice_key in (("tools", "tool_choice"), ("functions", "function_call")):
        if key in extra and not extra[key]:
            del extra[key]
            extra.pop(choice_key, None)
    restricted = request.model_copy()
    restricted.__pydantic_extra__ = extra
    return ChatTaintResult(request=restricted, tainted=True, removed=tuple(sorted(set(removed))), forced_sink=forced)
