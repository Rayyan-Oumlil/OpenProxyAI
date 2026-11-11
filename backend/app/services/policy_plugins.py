"""Org WebAssembly policy plugins in the policy decision (Phase 5, slice 5.11).

The org's policy lists its enabled plugins (id, name, hash). The module bytes live in ``policy_plugins`` and are fetched on first use and
kept in memory by hash, so a request normally touches no database. A plugin can only add a restriction: the built-in rules run first and
a plugin is asked only about a request they allowed. A plugin that fails (a crash, running out of time, a hash that does not match what
was uploaded) counts as having flagged the request: it blocks under ``enforce`` and is recorded under ``log_only``. It is never skipped.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select

from app.database import org_scoped_session
from app.models.policy_plugin import PolicyPlugin
from app.services import wasm_runtime

logger = logging.getLogger(__name__)

MAX_PLUGINS_PER_ORG = 5
_module_bytes: dict[str, bytes] = {}  # by sha256 of the content, so a changed module can never be mistaken for the old one


@dataclass(frozen=True)
class PluginFinding:
    name: str
    failed: bool  # True when the plugin could not give a verdict, False when it blocked


async def _bytes_for(org_id: uuid.UUID, plugin_id: str, sha256: str) -> bytes:
    cached = _module_bytes.get(sha256)
    if cached is not None:
        return cached
    async with org_scoped_session(org_id) as db:
        row = await db.scalar(select(PolicyPlugin).where(PolicyPlugin.id == uuid.UUID(plugin_id), PolicyPlugin.org_id == org_id))
    if row is None:
        raise wasm_runtime.WasmError("the plugin no longer exists")
    if wasm_runtime.sha256_of(row.module) != sha256:
        raise wasm_runtime.WasmError("the stored plugin does not match the version the policy lists")
    if len(_module_bytes) > 64:
        _module_bytes.pop(next(iter(_module_bytes)))
    _module_bytes[sha256] = row.module
    return row.module


async def run_plugins(org_id: uuid.UUID, plugins: list[dict], text: str) -> PluginFinding | None:
    """The first plugin that blocks or fails, or None when every plugin allowed the text."""
    for plugin in plugins:
        name = str(plugin.get("name", "unknown"))
        try:
            data = await _bytes_for(org_id, str(plugin["id"]), str(plugin["sha256"]))
            verdict = await asyncio.to_thread(wasm_runtime.evaluate, data, text)
        except (wasm_runtime.WasmError, KeyError, ValueError) as exc:
            logger.warning("policy plugin %s failed for org %s: %s", name, org_id, exc)
            return PluginFinding(name, failed=True)
        except Exception:  # noqa: BLE001  (a bug here must not become an allow)
            logger.exception("policy plugin %s raised unexpectedly for org %s", name, org_id)
            return PluginFinding(name, failed=True)
        if verdict.blocked:
            return PluginFinding(name, failed=False)
    return None


def forget() -> None:
    _module_bytes.clear()
