"""Running an org's WebAssembly policy plugin in a sandbox (Phase 5, slice 5.11).

A plugin is a pure function from text to a verdict. It can add a restriction to the built-in policy; it can never remove one.

The contract (a module that does not meet it is refused at upload):

    (memory (export "memory") ...)            linear memory the host writes the text into
    (func (export "alloc") (param i32) (result i32))     returns a pointer to ``len`` writable bytes
    (func (export "evaluate") (param i32 i32) (result i32))   (pointer, length) -> 0 allow, 1 block; anything else is an error

What the sandbox guarantees, whatever the module does:

- **No imports.** The module is instantiated with nothing to call: no files, no network, no clock, no randomness, no WASI. A module
  that declares an import does not link and is refused at upload.
- **Bounded CPU.** Each call gets a fixed amount of "fuel"; running out traps. An endless loop costs the same fixed amount as any other
  call, then stops.
- **Bounded memory.** The module's memory cannot grow past ``MEMORY_LIMIT_BYTES``.
- **No state between calls.** Every call gets a fresh instance, so a module cannot remember one request for the next, or leak one
  request's text into another.
- **Bounded input.** Text longer than ``MAX_INPUT_BYTES`` is refused rather than cut, so a plugin never judges half of a request.

Any failure is a ``WasmError``; the caller decides what a failure means (the policy engine treats it as a violation).
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass

from wasmtime import Config, Engine, Instance, Module, Store, Trap, WasmtimeError

MAX_MODULE_BYTES = 1024 * 1024
MAX_INPUT_BYTES = 256 * 1024
FUEL_PER_CALL = 20_000_000
MEMORY_LIMIT_BYTES = 16 * 1024 * 1024
ALLOW, BLOCK = 0, 1


class WasmError(Exception):
    """The module is invalid or misbehaved. The message is safe to show an admin; it never contains the text that was evaluated."""


@dataclass(frozen=True)
class Verdict:
    blocked: bool


_config = Config()
_config.consume_fuel = True
# Traps are implemented with explicit checks, not by catching signals. Signal-based traps would collide with the host's own handlers
# (Python's faulthandler, a profiler) and crash the whole process on the first trap, instead of failing one plugin call.
_config.signals_based_traps = False
_config.max_wasm_stack = 512 * 1024
# A policy plugin is plain computation on text; every feature it cannot need is switched off to keep the surface small.
for _feature in (
    "wasm_threads", "shared_memory", "wasm_component_model", "wasm_gc", "wasm_exceptions", "wasm_function_references", "wasm_stack_switching",
    "wasm_memory64", "wasm_multi_memory", "wasm_custom_page_sizes", "wasm_wide_arithmetic", "wasm_relaxed_simd", "wasm_tail_call",
):
    try:
        setattr(_config, _feature, False)
    except Exception:  # noqa: BLE001  (a feature this wasmtime build does not have is already off)
        pass
_engine = Engine(_config)
_compiled: dict[str, Module] = {}
_lock = threading.Lock()


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _compile(data: bytes) -> Module:
    if not data or len(data) > MAX_MODULE_BYTES:
        raise WasmError(f"a plugin must be between 1 byte and {MAX_MODULE_BYTES} bytes")
    try:
        return Module(_engine, data)
    except (WasmtimeError, TypeError, ValueError):
        raise WasmError("the file is not a valid WebAssembly module") from None


def _checked_exports(module: Module) -> None:
    if len(module.imports) > 0:
        raise WasmError("the plugin imports functions from the host, which is not allowed: a plugin can call nothing")
    exported = {export.name for export in module.exports}
    for required in ("memory", "alloc", "evaluate"):
        if required not in exported:
            raise WasmError(f"the plugin must export '{required}'")


def _instantiate(module: Module) -> tuple[Store, Instance]:
    store = Store(_engine)
    store.set_fuel(FUEL_PER_CALL)
    store.set_limits(memory_size=MEMORY_LIMIT_BYTES, instances=1, tables=4, table_elements=10_000, memories=1)
    try:
        return store, Instance(store, module, [])
    except (WasmtimeError, Trap):
        raise WasmError("the plugin could not be started (its start function failed or it needs more memory than allowed)") from None


def _call(module: Module, text: bytes) -> int:
    store, instance = _instantiate(module)
    exports = instance.exports(store)
    try:
        memory, alloc, evaluate = exports["memory"], exports["alloc"], exports["evaluate"]
        pointer = alloc(store, len(text))
        if not isinstance(pointer, int) or pointer < 0 or pointer + len(text) > memory.data_len(store):
            raise WasmError("the plugin's 'alloc' returned a pointer outside its own memory")
        if text:
            memory.write(store, text, pointer)
        verdict = evaluate(store, pointer, len(text))
    except Trap as exc:
        out_of_fuel = "fuel" in str(exc).lower()
        raise WasmError("the plugin used up its time allowance" if out_of_fuel else "the plugin crashed (a WebAssembly trap)") from None
    except WasmtimeError:
        raise WasmError("the plugin failed while running") from None
    except (TypeError, ValueError):
        raise WasmError("the plugin's functions do not have the expected signatures") from None
    if verdict not in (ALLOW, BLOCK):
        raise WasmError(f"the plugin returned {verdict!r}; it must return 0 (allow) or 1 (block)")
    return verdict


def validate(data: bytes) -> str:
    """Accepts a module only if it meets the contract and answers a call; returns its SHA-256. Raises ``WasmError`` otherwise."""
    module = _compile(data)
    _checked_exports(module)
    _call(module, b"")
    return sha256_of(data)


def evaluate(data: bytes, text: str) -> Verdict:
    """Runs the plugin on ``text`` in a fresh instance. Raises ``WasmError`` on any failure; never returns a guess."""
    encoded = text.encode("utf-8")
    if len(encoded) > MAX_INPUT_BYTES:
        raise WasmError(f"the request is longer than the {MAX_INPUT_BYTES} bytes a plugin can judge")
    key = sha256_of(data)
    with _lock:
        module = _compiled.get(key)
        if module is None:
            module = _compile(data)
            _checked_exports(module)
            _compiled[key] = module
            if len(_compiled) > 64:
                _compiled.pop(next(iter(_compiled)))
    return Verdict(blocked=_call(module, encoded) == BLOCK)
