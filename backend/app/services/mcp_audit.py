"""Audit trail for MCP tool calls: one request_logs row per tools/call (spec M5)."""

from __future__ import annotations

import uuid

from app.database import org_scoped_session
from app.models.request_log import RequestLog
from app.services.mcp_gateway import ToolCallOutcome


async def record_tool_call(
	*,
	org_id: uuid.UUID,
	user_id: uuid.UUID,
	api_key_id: uuid.UUID | None,
	outcome: ToolCallOutcome,
	latency_ms: int,
) -> None:
	"""Write the audit row. Runs as a background task with its own org-scoped session."""
	metadata: dict = {"type": "mcp_tool_call", "tool": outcome.tool, "server": outcome.server}
	if outcome.decision is not None:
		metadata.update(outcome.decision.as_metadata())
	async with org_scoped_session(org_id) as session:
		session.add(RequestLog(
			request_id=uuid.uuid4(),
			org_id=org_id,
			user_id=user_id,
			api_key_id=api_key_id,
			model=outcome.tool[:100],
			provider=f"mcp:{outcome.server or 'unknown'}"[:50],
			prompt_tokens=0,
			completion_tokens=0,
			total_tokens=0,
			cost_usd=0,
			latency_ms=latency_ms,
			status_code=outcome.status_code,
			error_message=(outcome.error or {}).get("message"),
			request_metadata=metadata,
		))
		await session.commit()
