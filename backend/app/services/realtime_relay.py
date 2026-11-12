"""The realtime relay: carries one live session between a client and the provider, applying the gateway's rules to each event.

Kept free of FastAPI, the database and the provider so every rule is testable with in-memory sockets. The route supplies the sockets
and the ``Hooks`` (policy, limits, usage recording, "is this key still good").

What the relay guarantees:

- Only known client event types reach the provider; anything else is refused with an ``error`` event (fail closed).
- Every string a client can put in an event is handed to ``scan`` first; audio is opaque and is not.
- A response is admitted by the limits before it starts: when the client asks (``response.create``), and when the provider starts one on
  its own (server-side voice detection), which is cancelled if refused.
- No event can change the model the session was admitted for.
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
# The one thing left out of the text scan: the base64 audio payload. Every other string, whatever its key, is scanned: a key name says
# what a field is usually for, not what a client put in it.
_AUDIO_KEY = "audio"


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
	"""Every string in an event except the audio payload."""
	if key == _AUDIO_KEY and isinstance(value, str):
		return []
	if isinstance(value, str):
		return [value] if value else []
	if isinstance(value, dict):
		return [t for k, v in value.items() for t in texts_of(v, k)]
	if isinstance(value, list):
		return [t for v in value for t in texts_of(v, None if key == _AUDIO_KEY else key)]  # only a direct string under audio is skipped
	return []


def models_named(value: Any, key: str | None = None) -> list[str]:
	"""Every ``model`` value in an event, at any depth."""
	if isinstance(value, dict):
		return [m for k, v in value.items() for m in models_named(v, k)]
	if isinstance(value, list):
		return [m for v in value for m in models_named(v, key)]
	return [value] if key == "model" and isinstance(value, str) else []


def error_event(code: str, message: str, event_id: str | None) -> str:
	return json.dumps({"type": "error", "error": {"type": "invalid_request_error", "code": code, "message": message, "event_id": event_id}})


def _size(data: str | bytes) -> int:
	return len(data) if isinstance(data, (bytes, bytearray)) else len(data.encode("utf-8"))


class _Pending:
	"""Responses the client asked for that the provider has not yet announced: those were admitted when asked, and must not be admitted again."""

	def __init__(self) -> None:
		self.count = 0
		self.refused: set[str] = set()  # responses cancelled for the limits: nothing of theirs reaches the client


async def _client_to_provider(client: Any, upstream: Any, hooks: Hooks, max_bytes: int, model_name: str, pending: _Pending) -> None:
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
		if any(m not in (model_name, f"openai/{model_name}") for m in models_named(event)):
			await client.send_text(error_event("model_not_allowed", "The model of a session cannot be changed after it is admitted", event_id))
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
			pending.count += 1
		await upstream.send(json.dumps(event))  # the checked event, not the raw text: a duplicated key must not read two ways


async def _provider_to_client(client: Any, upstream: Any, hooks: Hooks, pending: _Pending) -> None:
	while True:
		frame = await upstream.recv()
		event = _event_of(frame, always=bool(pending.refused))
		kind = event.get("type") if event else None
		if event is not None and pending.refused:
			response = event.get("response") if isinstance(event.get("response"), dict) else {}
			rid = response.get("id") if kind in ("response.created", "response.done") else event.get("response_id")
			if rid in pending.refused:
				if kind == "response.done":
					pending.refused.discard(rid)
					await hooks.record_response(response)  # it was cancelled, not free
				continue
		if kind == "response.created" and pending.count == 0:
			# The provider started a response nobody asked for (server-side voice detection answers on its own). It is subject to the
			# same limits as one the client asked for: refused means cancelled, and the client is told instead of being shown it.
			reason = await hooks.admit_response()
			if reason:
				rid = (event.get("response") or {}).get("id") if isinstance(event.get("response"), dict) else None
				if isinstance(rid, str):
					pending.refused.add(rid)
				await upstream.send(json.dumps({"type": "response.cancel"}))
				await client.send_text(error_event("limit_exceeded", f"Response cancelled: {reason}", None))
				continue
		elif kind == "response.created":
			pending.count -= 1
		elif kind == "error" and pending.count > 0:
			pending.count -= 1  # the request that failed never produces response.created; checking one response too many is the safe side
		await client.send_text(frame)
		if kind == "response.done" and isinstance(event.get("response"), dict):
			await hooks.record_response(event["response"])


def _event_of(frame: str | bytes, always: bool = False) -> dict | None:
	if not isinstance(frame, str) or not frame.startswith("{"):
		return None
	if not always and not any(marker in frame for marker in ('"response.created"', '"response.done"', '"error"')):
		return None
	try:
		event = json.loads(frame)
	except ValueError:
		return None
	return event if isinstance(event, dict) else None


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


async def relay(client: Any, upstream: Any, hooks: Hooks, *, model_name: str, max_message_bytes: int, max_seconds: float, check_every: float) -> tuple[int, str]:
	"""Runs the session until one side ends it. Returns the close code and reason that were sent."""
	pending = _Pending()
	tasks = [
		asyncio.create_task(_client_to_provider(client, upstream, hooks, max_message_bytes, model_name, pending)),
		asyncio.create_task(_provider_to_client(client, upstream, hooks, pending)),
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
