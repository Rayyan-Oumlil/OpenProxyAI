"""Per-tool grants and request-time narrowing for the MCP gateway (design-specs A.5).

Layers, outermost first. Each can only remove tools the previous one allowed:

    1. organisation policy   mcp_allowed_tools / mcp_blocked_tools   (policy_service, unchanged)
    2. grants                tool_grants rows that apply to the caller (role, team, user or API key)
    3. request scope         ``X-OpenProxy-MCP-Tools`` header, a comma-separated list of patterns

Rules for layer 2:
    * a matching ``deny`` always wins;
    * if any ``allow`` grant applies to the caller, the tool must match one of them; with no applicable
      ``allow`` grant the caller is not restricted (grants are opt-in, enabling them breaks nobody).

Layer 3 is an intersection, so a client can ask for less than it was granted but never for more.
Patterns are fnmatch globs over the namespaced tool name (``<server>__<tool>``).
"""

from __future__ import annotations

import fnmatch
import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_grant import ToolGrant

SCOPE_HEADER = "X-OpenProxy-MCP-Tools"
SUBJECT_TYPES = ("role", "team", "user", "api_key")
EFFECTS = ("allow", "deny")
PATTERN_RE = re.compile(r"^[A-Za-z0-9_*?.\-]{1,200}$")
MAX_SCOPE_PATTERNS = 50
MAX_SUMMARY_PATTERNS = 50

REASON_DENIED = "tool_grant_denied"
REASON_NOT_GRANTED = "tool_not_granted"
REASON_OUT_OF_SCOPE = "tool_out_of_scope"
REASON_OUT_OF_BUNDLE = "tool_not_in_bundle"


class ScopeHeaderError(ValueError):
    """The narrowing header is present but unusable (the route answers 400)."""


@dataclass(frozen=True)
class GrantRule:
    subject_type: str
    subject_id: str
    tool_pattern: str
    effect: str


@dataclass(frozen=True)
class Caller:
    user_id: uuid.UUID
    role: str
    team_id: uuid.UUID | None
    api_key_id: uuid.UUID | None

    def subjects(self) -> set[tuple[str, str]]:
        found = {("role", self.role), ("user", str(self.user_id))}
        if self.team_id is not None:
            found.add(("team", str(self.team_id)))
        if self.api_key_id is not None:
            found.add(("api_key", str(self.api_key_id)))
        return found


@dataclass(frozen=True)
class AccessVerdict:
    allowed: bool
    reason: str | None = None


def _matches(name: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


@dataclass(frozen=True)
class ToolAccess:
    """The effective access of one request: grants that apply to the caller plus the optional scope."""

    allow: tuple[str, ...] = ()
    deny: tuple[str, ...] = ()
    scope: tuple[str, ...] | None = None
    bundle: tuple[str, ...] | None = None  # patterns of the bundle endpoint in use; () allows nothing

    def check(self, tool_name: str) -> AccessVerdict:
        if _matches(tool_name, self.deny):
            return AccessVerdict(False, REASON_DENIED)
        if self.allow and not _matches(tool_name, self.allow):
            return AccessVerdict(False, REASON_NOT_GRANTED)
        if self.scope is not None and not _matches(tool_name, self.scope):
            return AccessVerdict(False, REASON_OUT_OF_SCOPE)
        if self.bundle is not None and not _matches(tool_name, self.bundle):
            return AccessVerdict(False, REASON_OUT_OF_BUNDLE)
        return AccessVerdict(True)

    def summary(self) -> dict[str, Any]:
        """What the audit row records: the patterns that applied to this request."""
        def cap(values: Iterable[str]) -> list[str]:
            return sorted(values)[:MAX_SUMMARY_PATTERNS]

        out: dict[str, Any] = {"allow": cap(self.allow), "deny": cap(self.deny)}
        if self.scope is not None:
            out["scope"] = cap(self.scope)
        if self.bundle is not None:
            out["bundle_patterns"] = cap(self.bundle)
        return out


def build_access(
    rules: Iterable[GrantRule],
    caller: Caller,
    scope: tuple[str, ...] | None = None,
    bundle: tuple[str, ...] | None = None,
) -> ToolAccess:
    subjects = caller.subjects()
    applicable = [r for r in rules if (r.subject_type, r.subject_id) in subjects]
    return ToolAccess(
        allow=tuple(sorted({r.tool_pattern for r in applicable if r.effect == "allow"})),
        deny=tuple(sorted({r.tool_pattern for r in applicable if r.effect == "deny"})),
        scope=scope,
        bundle=bundle,
    )


def parse_scope_header(values: list[str]) -> tuple[str, ...] | None:
    """Parse every ``X-OpenProxy-MCP-Tools`` header value. None when the header is absent.

    Strict on purpose: a malformed narrowing header must fail the request, never be silently ignored,
    because ignoring it would hand the caller a wider tool set than they asked for.
    """
    if not values:
        return None
    if len(values) > 1:
        raise ScopeHeaderError(f"{SCOPE_HEADER} must be sent once")
    patterns = [p.strip() for p in values[0].split(",")]
    if not patterns or any(not PATTERN_RE.fullmatch(p) for p in patterns):
        raise ScopeHeaderError(f"{SCOPE_HEADER} must be a comma-separated list of tool name patterns")
    if len(patterns) > MAX_SCOPE_PATTERNS:
        raise ScopeHeaderError(f"{SCOPE_HEADER} accepts at most {MAX_SCOPE_PATTERNS} patterns")
    return tuple(dict.fromkeys(patterns))


async def load_grants(db: AsyncSession, org_id: uuid.UUID) -> list[GrantRule]:
    rows = await db.scalars(select(ToolGrant).where(ToolGrant.org_id == org_id))
    return [GrantRule(r.subject_type, r.subject_id, r.tool_pattern, r.effect) for r in rows.all()]
