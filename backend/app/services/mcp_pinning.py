"""Tool description pinning and drift detection (design-specs A.3).

Agents must never see a tool description the org has not approved: a server that changes a description
after approval (rug-pull) or ships a poisoned one is hidden or served from the approved snapshot.

pin_mode per server:
    off      no pinning, live definitions are served (previous behaviour)
    warn     trust on first use: a new tool is approved automatically; later changes mark it ``drifted``,
             the approved snapshot keeps being served and calls still go through (flagged in the audit row)
    enforce  nothing is trusted until an admin approves it; pending/drifted/blocked tools are hidden and
             their calls are refused with JSON-RPC -32004

A tool an admin blocked is refused in warn and enforce modes alike.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_tool import McpTool, McpToolVersion

if TYPE_CHECKING:
    from app.services.mcp_gateway import UpstreamServer

logger = logging.getLogger(__name__)

PIN_OFF, PIN_WARN, PIN_ENFORCE = "off", "warn", "enforce"
PIN_MODES = (PIN_OFF, PIN_WARN, PIN_ENFORCE)
PENDING, APPROVED, DRIFTED, BLOCKED = "pending", "approved", "drifted", "blocked"
MAX_TOOL_NAME_LENGTH = 200


@dataclass(frozen=True)
class ToolPin:
    name: str
    status: str
    snapshot: dict[str, Any] | None  # the approved tool object, as advertised when it was approved


def definition_hash(tool: dict[str, Any]) -> str:
    """sha256 over the canonical JSON of the whole tool object (any field can carry instructions)."""
    canonical = json.dumps(tool, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def served_snapshot(pin: ToolPin | None, mode: str) -> dict[str, Any] | None:
    """What tools/list may show for this tool: the approved snapshot, or nothing."""
    if pin is None or pin.snapshot is None:
        return None
    if pin.status == APPROVED or (pin.status == DRIFTED and mode == PIN_WARN):
        return pin.snapshot
    return None


def call_gate(pin: ToolPin | None, mode: str) -> tuple[bool, str]:
    """(allowed, label) for a tools/call. The label goes into the audit row."""
    label = pin.status if pin is not None else "unpinned"
    if pin is not None and pin.status == BLOCKED:
        return False, label
    if mode == PIN_ENFORCE:
        return pin is not None and pin.status == APPROVED, label
    return True, label


def _pin_of(row: McpTool) -> ToolPin:
    return ToolPin(name=row.name, status=row.status, snapshot=row.approved_snapshot)


class DbPinStore:
    """Pin state in Postgres. The session must already be scoped to ``org_id`` (RLS)."""

    def __init__(self, db: AsyncSession, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    async def _rows(self, server_id: uuid.UUID) -> dict[str, McpTool]:
        rows = await self._db.scalars(
            select(McpTool).where(McpTool.org_id == self._org_id, McpTool.server_id == server_id)
        )
        return {row.name: row for row in rows.all()}

    async def get(self, server: UpstreamServer, tool_name: str) -> ToolPin | None:
        row = await self._db.scalar(
            select(McpTool).where(
                McpTool.org_id == self._org_id, McpTool.server_id == server.id, McpTool.name == tool_name
            )
        )
        return _pin_of(row) if row is not None else None

    async def reconcile(self, server: UpstreamServer, live: list[dict[str, Any]]) -> dict[str, ToolPin]:
        """Record what the upstream advertises and return the pin state for each advertised tool.

        The caller commits. Tools that disappeared upstream keep their row (and their approval).
        """
        existing = await self._rows(server.id)
        known_hashes = await self._known_hashes([row.id for row in existing.values()])
        now = datetime.now(UTC).replace(tzinfo=None)
        result: dict[str, ToolPin] = {}

        for tool in live:
            name = tool.get("name") if isinstance(tool, dict) else None
            if not isinstance(name, str) or not name or len(name) > MAX_TOOL_NAME_LENGTH:
                continue
            digest = definition_hash(tool)
            row = existing.get(name)
            if row is None:
                row = await self._insert_tool(server, name, tool, digest, now)
                existing[name] = row
            else:
                row.last_seen_at = now
                if row.current_hash != digest:
                    row.definition = tool
                    row.current_hash = digest
            if (row.id, digest) not in known_hashes:
                await self._record_version(row, digest, tool)
                known_hashes.add((row.id, digest))

            self._settle(row, server)
            result[name] = _pin_of(row)
        await self._db.flush()
        return result

    async def _insert_tool(
        self, server: UpstreamServer, name: str, tool: dict[str, Any], digest: str, now: datetime
    ) -> McpTool:
        """Insert the row; if a concurrent request won the race, use theirs (a savepoint keeps the txn alive)."""
        row = McpTool(
            org_id=self._org_id, server_id=server.id, name=name, definition=tool, current_hash=digest,
            status=PENDING, first_seen_at=now, last_seen_at=now,
        )
        try:
            async with self._db.begin_nested():
                self._db.add(row)
        except IntegrityError:
            winner = await self._db.scalar(
                select(McpTool).where(
                    McpTool.org_id == self._org_id, McpTool.server_id == server.id, McpTool.name == name
                )
            )
            if winner is None:
                raise
            return winner
        return row

    async def _record_version(self, row: McpTool, digest: str, tool: dict[str, Any]) -> None:
        try:
            async with self._db.begin_nested():
                self._db.add(McpToolVersion(org_id=self._org_id, tool_id=row.id, hash=digest, definition=tool))
        except IntegrityError:
            pass  # a concurrent request recorded the same definition

    def _settle(self, row: McpTool, server: UpstreamServer) -> None:
        """Move ``row`` to the status its hashes and the server's pin_mode imply."""
        if row.status == BLOCKED:
            return
        if row.approved_hash == row.current_hash:
            row.status = APPROVED
        elif row.approved_hash is None and server.pin_mode == PIN_WARN:
            _approve(row, by=None)  # trust on first use
        elif row.approved_hash is None:
            row.status = PENDING
        else:
            if row.status != DRIFTED:
                logger.warning(
                    "MCP tool drift: server=%s tool=%s approved=%s live=%s",
                    server.name, row.name, row.approved_hash[:12], row.current_hash[:12],
                )
            row.status = DRIFTED

    async def _known_hashes(self, tool_ids: list[uuid.UUID]) -> set[tuple[uuid.UUID, str]]:
        if not tool_ids:
            return set()
        rows = await self._db.execute(
            select(McpToolVersion.tool_id, McpToolVersion.hash).where(McpToolVersion.tool_id.in_(tool_ids))
        )
        return {(tool_id, digest) for tool_id, digest in rows.all()}


def _approve(row: McpTool, by: uuid.UUID | None) -> None:
    row.approved_hash = row.current_hash
    row.approved_snapshot = row.definition
    row.status = APPROVED
    row.approved_by = by
    row.approved_at = datetime.now(UTC).replace(tzinfo=None)


def approve_tool(row: McpTool, by: uuid.UUID) -> None:
    """Approve the definition currently advertised (also unblocks a blocked tool)."""
    _approve(row, by)


def block_tool(row: McpTool) -> None:
    row.status = BLOCKED
