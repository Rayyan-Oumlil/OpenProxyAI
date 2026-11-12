"""The realtime relay: carries one live session between a client and the provider, applying the gateway's rules to each event.

Kept free of FastAPI, the database and the provider so every rule is testable with in-memory sockets. The route supplies the sockets
and the ``Hooks`` (policy, limits, usage recording, "is this key still good").

What the relay guarantees:

- Only known client event types reach the provider; anything else is refused with an ``error`` event (fail closed).
- Every string a client can put in an event is handed to ``scan`` first; audio is opaque and is not.
- ``response.create`` is admitted by the limits before the provider is asked to speak.
- Each ``response.done`` is recorded exactly once. If recording fails the session ends: usage that cannot be counted is not given away.
- A session ends at its time limit, or when the credentials stop being valid, whichever comes first.
- Nothing from an internal failure is sent to the client.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.utils.logging import get_logger

logger = get_logger(__name__)


class Disconnected(Exception):
	"""The other end of a socket is gone."""


CLIENT_EVENTS = frozenset({
	"session.update", "input_audio_buffer.append", "input_audio_buffer.commit", "input_audio_buffer.clear",
	"conversation.item.create", "conversation.item.truncate", "conversation.item.delete", "conversation.item.retrieve",
	"response.create", "response.cancel",
})
# Keys whose values are not text a person wrote: audio payloads and identifiers.
_NOT_TEXT = frozenset({"audio", "event_id", "type", "id", "previous_item_id", "item_id", "call_id", "voice", "model", "object", "role", "status", "format"})


@dataclass(frozen=True)
class Hooks:
	scan: Callable[[str], Awaitable[str | None]]  # text -> reason it is refused, or None
	admit_response: Callable[[], Awaitable[str | None]]  # -> reason a new response may not start, or None
	record_response: Callable[[dict], Awaitable[None]]  # the ``response`` object of a response.done
	still_valid: Callable[[], Awaitable[bool]]  # the credentials, the policy and the key are still good


class _End(Exception):
	def __init__(self, code: int, reason: str) -> None:
		self.code, self.reason = code, reason


def texts_of(value: Any, key: str | None = None) -> list[str]:
	"""Every string a person could have written in an event, leaving out audio and identifiers."""
	if key in _NOT_TEXT:
		return []
	if isinstance(value, str):
		return [value] if value else []
	if isinstance(value, dict):
		return [t for k, v in value.items() for t in texts_of(v, k)]
	if isinstance(value, list):
		return [t for v in value for t in texts_of(v, key)]
	return []


def error_event(code: str, message: str, event_id: str | None) -> str:
	return json.dumps({"type": "error", "error": {"type": "invalid_request_error", "code": code, "message": message, "event_id": event_id}})


def _size(data: str | bytes) -> int:
	return len(data) if isinstance(data, (bytes, bytearray)) else len(data.encode("utf-8"))


async def _client_to_provider(client: Any, upstream: Any, hooks: Hooks, max_bytes: int) -> None:
	while True:
		frame = await client.receive()
		if isinstance(frame, (bytes, bytearray)):
			raise _End(1003, "binary_frames_not_supported")
		if _size(frame) > max_bytes:
			raise _End(1009, "message_too_large")
		try:
			event = json.loads(frame)
		except ValueError:
			raise _End(1007, "not_json") from None
		if not isinstance(event, dict) or not isinstance(event.get("type"), str):
			raise _End(1007, "not_an_event")
		event_id = event.get("event_id") if isinstance(event.get("event_id"), str) else None
		if event["type"] not in CLIENT_EVENTS:
			await client.send_text(error_event("unsupported_event", f"Event type '{event['type'][:64]}' is not supported through the gateway", event_id))
			continue
		text = "\n".join(texts_of(event))
		if text:
			reason = await hooks.scan(text)
			if reason:
				await client.send_text(error_event("policy_violation", f"Refused by policy ({reason})", event_id))
				continue
		if event["type"] == "response.create":
			reason = await hooks.admit_response()
			if reason:
				await client.send_text(error_event("limit_exceeded", f"Response not started: {reason}", event_id))
				continue
		await upstream.send(frame)


async def _provider_to_client(client: Any, upstream: Any, hooks: Hooks) -> None:
	while True:
		frame = await upstream.recv()
		await client.send_text(frame)
		if isinstance(frame, str) and '"response.done"' in frame:
			try:
				event = json.loads(frame)
			except ValueError:
				continue
			if isinstance(event, dict) and event.get("type") == "response.done" and isinstance(event.get("response"), dict):
				await hooks.record_response(event["response"])


async def _limits(hooks: Hooks, max_seconds: float, check_every: float) -> None:
	loop = asyncio.get_running_loop()
	deadline = loop.time() + max_seconds
	while True:
		remaining = deadline - loop.time()
		if remaining <= 0:
			raise _End(1008, "session_time_limit")
		await asyncio.sleep(min(check_every, remaining))
		if loop.time() >= deadline:
			raise _End(1008, "session_time_limit")
		if not await hooks.still_valid():
			raise _End(1008, "credentials_no_longer_valid")


async def _close(socket: Any, code: int, reason: str) -> None:
	try:
		await socket.close(code, reason)
	except Exception:  # noqa: BLE001  (already closed or broken: nothing more to do)
		pass


async def relay(client: Any, upstream: Any, hooks: Hooks, *, max_message_bytes: int, max_seconds: float, check_every: float) -> tuple[int, str]:
	"""Runs the session until one side ends it. Returns the close code and reason that were sent."""
	tasks = [
		asyncio.create_task(_client_to_provider(client, upstream, hooks, max_message_bytes)),
		asyncio.create_task(_provider_to_client(client, upstream, hooks)),
		asyncio.create_task(_limits(hooks, max_seconds, check_every)),
	]
	try:
		done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
	finally:
		for task in tasks:
			task.cancel()
		await asyncio.gather(*tasks, return_exceptions=True)
	exc = next(iter(done)).exception()
	if isinstance(exc, _End):
		code, reason = exc.code, exc.reason
	elif isinstance(exc, Disconnected) or exc is None:
		code, reason = 1000, "closed"
	else:
		logger.error("realtime session failed: %s", type(exc).__name__, exc_info=exc)
		code, reason = 1011, "internal_error"
	await _close(client, code, reason)
	await _close(upstream, code, reason)
	return code, reason
