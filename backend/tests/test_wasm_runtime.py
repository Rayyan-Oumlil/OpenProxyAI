"""The WebAssembly sandbox with real modules: what a plugin can and cannot do (Phase 5, slice 5.11)."""

from __future__ import annotations

import time

import pytest

wasmtime = pytest.importorskip("wasmtime")

from app.services import wasm_runtime as wr  # noqa: E402

PRELUDE = '''
  (memory (export "memory") 8)
  (global $next (mut i32) (i32.const 1024))
  (func (export "alloc") (param $n i32) (result i32)
    (local $p i32)
    (local.set $p (global.get $next))
    (global.set $next (i32.add (global.get $next) (local.get $n)))
    (local.get $p))
'''


def module(body: str, prelude: str = PRELUDE) -> bytes:
	return wasmtime.wat2wasm(f"(module {prelude} {body})")


# Blocks when the text contains an "X" (byte 88).
BLOCK_X = module('''
  (func (export "evaluate") (param $ptr i32) (param $len i32) (result i32)
    (local $i i32)
    (block $done
      (loop $l
        (br_if $done (i32.ge_u (local.get $i) (local.get $len)))
        (if (i32.eq (i32.load8_u (i32.add (local.get $ptr) (local.get $i))) (i32.const 88))
          (then (return (i32.const 1))))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $l)))
    (i32.const 0))''')
ALLOW_ALL = module('(func (export "evaluate") (param i32 i32) (result i32) (i32.const 0))')
BLOCK_ALL = module('(func (export "evaluate") (param i32 i32) (result i32) (i32.const 1))')
ENDLESS = module('(func (export "evaluate") (param i32 i32) (result i32) (loop $l (br $l)) (i32.const 0))')
TRAPS = module('(func (export "evaluate") (param i32 i32) (result i32) unreachable)')
BAD_VERDICT = module('(func (export "evaluate") (param i32 i32) (result i32) (i32.const 7))')
# Counts calls in a global: if state survived between calls the second call would see 1.
REMEMBERS = module('''
  (global $calls (mut i32) (i32.const 0))
  (func (export "evaluate") (param i32 i32) (result i32)
    (global.set $calls (i32.add (global.get $calls) (i32.const 1)))
    (if (result i32) (i32.gt_u (global.get $calls) (i32.const 1)) (then (i32.const 1)) (else (i32.const 0))))''')
# 300 pages is about 19 MB, more than the 16 MB limit and far less than anything else would stop it at.
GROWS = module('''
  (func (export "evaluate") (param i32 i32) (result i32)
    (if (result i32) (i32.eq (memory.grow (i32.const 300)) (i32.const -1)) (then (i32.const 0)) (else (i32.const 1))))''',
  PRELUDE.replace('(memory (export "memory") 8)', '(memory (export "memory") 8 2000)'))
WANTS_IMPORT = wasmtime.wat2wasm('''(module (import "env" "log" (func $log (param i32)))
  (memory (export "memory") 1) (func (export "alloc") (param i32) (result i32) (i32.const 0))
  (func (export "evaluate") (param i32 i32) (result i32) (call $log (i32.const 1)) (i32.const 0)))''')
WANTS_WASI = wasmtime.wat2wasm('''(module (import "wasi_snapshot_preview1" "fd_write" (func (param i32 i32 i32 i32) (result i32)))
  (memory (export "memory") 1) (func (export "alloc") (param i32) (result i32) (i32.const 0))
  (func (export "evaluate") (param i32 i32) (result i32) (i32.const 0)))''')
NO_EVALUATE = wasmtime.wat2wasm('(module (memory (export "memory") 1) (func (export "alloc") (param i32) (result i32) (i32.const 0)))')
NO_MEMORY = wasmtime.wat2wasm('(module (func (export "alloc") (param i32) (result i32) (i32.const 0)) (func (export "evaluate") (param i32 i32) (result i32) (i32.const 0)))')
WRONG_SIGNATURE = module('(func (export "evaluate") (param i32) (result i32) (i32.const 0))')
WILD_ALLOC = wasmtime.wat2wasm('''(module (memory (export "memory") 1)
  (func (export "alloc") (param i32) (result i32) (i32.const 100000000))
  (func (export "evaluate") (param i32 i32) (result i32) (i32.const 0)))''')
START_TRAPS = wasmtime.wat2wasm('''(module (memory (export "memory") 1) (func $s unreachable) (start $s)
  (func (export "alloc") (param i32) (result i32) (i32.const 0)) (func (export "evaluate") (param i32 i32) (result i32) (i32.const 0)))''')


def test_a_plugin_that_blocks_on_a_marker_blocks_and_otherwise_allows():
	assert wr.evaluate(BLOCK_X, "nothing to see").blocked is False
	assert wr.evaluate(BLOCK_X, "contains an X here").blocked is True
	assert wr.evaluate(BLOCK_X, "").blocked is False


def test_multibyte_text_reaches_the_plugin_as_utf8():
	assert wr.evaluate(BLOCK_X, "héllo wörld, ünïcode 日本語 and X").blocked is True
	assert wr.evaluate(BLOCK_X, "héllo wörld, ünïcode 日本語").blocked is False


def test_an_endless_loop_is_stopped_by_fuel_not_left_running():
	started = time.monotonic()
	with pytest.raises(wr.WasmError, match="time allowance"):
		wr.evaluate(ENDLESS, "x")
	assert time.monotonic() - started < 10


def test_memory_cannot_grow_past_the_limit():
	# memory.grow past the limit must fail (-1), so the module takes the "allow" branch instead of the "block" one.
	assert wr.evaluate(GROWS, "x").blocked is False


def test_a_crash_is_an_error_that_does_not_contain_the_text():
	with pytest.raises(wr.WasmError, match="crashed") as caught:
		wr.evaluate(TRAPS, "a very secret sentence")
	assert "secret" not in str(caught.value)


def test_a_verdict_other_than_allow_or_block_is_an_error_not_a_guess():
	with pytest.raises(wr.WasmError, match="return 0"):
		wr.evaluate(BAD_VERDICT, "x")


def test_nothing_is_remembered_between_calls():
	"""Every call gets a fresh instance, so one request's text and state cannot reach the next."""
	assert [wr.evaluate(REMEMBERS, "x").blocked for _ in range(4)] == [False, False, False, False]


@pytest.mark.parametrize("data,message", [
	(WANTS_IMPORT, "imports"), (WANTS_WASI, "imports"), (NO_EVALUATE, "'evaluate'"), (NO_MEMORY, "'memory'"),
	(b"", "between 1 byte"), (b"not wasm at all", "not a valid"), (b"\x00asm\x01\x00\x00\x00garbage", "not a valid"),
])
def test_a_module_that_does_not_meet_the_contract_is_refused_at_upload(data, message):
	with pytest.raises(wr.WasmError, match=message):
		wr.validate(data)


@pytest.mark.parametrize("data", [WRONG_SIGNATURE, WILD_ALLOC, START_TRAPS, TRAPS, BAD_VERDICT, ENDLESS])
def test_a_module_that_cannot_answer_a_call_is_refused_at_upload(data):
	with pytest.raises(wr.WasmError):
		wr.validate(data)


def test_a_good_module_validates_and_reports_its_hash():
	assert wr.validate(BLOCK_X) == wr.sha256_of(BLOCK_X) and len(wr.sha256_of(BLOCK_X)) == 64
	wr.validate(ALLOW_ALL)
	wr.validate(BLOCK_ALL)


def test_a_module_over_the_size_limit_is_refused():
	with pytest.raises(wr.WasmError, match="between 1 byte"):
		wr.validate(b"\x00" * (wr.MAX_MODULE_BYTES + 1))


def test_text_longer_than_a_plugin_can_judge_is_refused_not_truncated():
	with pytest.raises(wr.WasmError, match="longer than"):
		wr.evaluate(ALLOW_ALL, "a" * (wr.MAX_INPUT_BYTES + 1))
	assert wr.evaluate(BLOCK_X, "a" * (wr.MAX_INPUT_BYTES - 1) + "X").blocked is True  # right up to the limit it sees everything


def test_a_pointer_outside_the_modules_own_memory_is_an_error():
	with pytest.raises(wr.WasmError, match="outside"):
		wr.evaluate(WILD_ALLOC, "hello")


def test_the_compiled_module_is_reused_but_a_different_module_is_never_confused_with_it():
	assert wr.evaluate(ALLOW_ALL, "X").blocked is False
	assert wr.evaluate(BLOCK_ALL, "X").blocked is True  # a different hash, a different module
	assert wr.evaluate(ALLOW_ALL, "X").blocked is False
