---
title: Policy plugins (WebAssembly)
description: Add your own rule to the policy check as a sandboxed WebAssembly module.
---

# Policy plugins (WebAssembly)

The built-in policy covers allowlists, keywords, personal data and injection. A **plugin** lets an organization add one more rule of its own: a small WebAssembly module that reads the text of a request and says *allow* or *block*. It runs on chat and on every other endpoint, because they all share the same policy check.

A plugin can only **add** a restriction. The built-in rules run first; the plugin is asked only about a request they allowed, so it can never lift a block. It is asked in `enforce` and `log_only` mode (under `log_only` a hit is recorded, not enforced) and never when policy is off.

## The sandbox

A plugin is untrusted code, so it is run so that the worst it can do is fail:

| Guarantee | |
|---|---|
| **Nothing to call** | No imports at all: no files, no network, no clock, no randomness, no WASI. A module that imports anything is refused at upload. |
| **Bounded time** | A fixed amount of work per call ("fuel"). An endless loop stops, with an error, after the same budget as any other call. |
| **Bounded memory** | The module cannot grow its memory past 16 MB. |
| **No memory between calls** | Every call is a fresh instance. A plugin cannot remember one request for the next. |
| **Whole text only** | Text over 256 KB is refused rather than cut, so a plugin never judges half a request. |
| **Fails closed** | A plugin that crashes, runs out of time, or whose stored bytes no longer match the hash in the policy counts as a hit: it **blocks under `enforce`** and is recorded. It is never skipped. |

## The contract

Export three things:

```wat
(memory (export "memory") 8)                                   ;; the host writes the text here
(func (export "alloc") (param i32) (result i32) ...)           ;; returns a pointer to that many writable bytes
(func (export "evaluate") (param i32 i32) (result i32) ...)    ;; (pointer, length) -> 0 allow, 1 block
```

The text is UTF-8. Any other return value is an error. A complete plugin that blocks any text containing a capital `X`:

```wat
(module
  (memory (export "memory") 8)
  (global $next (mut i32) (i32.const 1024))
  (func (export "alloc") (param $n i32) (result i32)
    (local $p i32)
    (local.set $p (global.get $next))
    (global.set $next (i32.add (global.get $next) (local.get $n)))
    (local.get $p))
  (func (export "evaluate") (param $ptr i32) (param $len i32) (result i32)
    (local $i i32)
    (block $done
      (loop $l
        (br_if $done (i32.ge_u (local.get $i) (local.get $len)))
        (if (i32.eq (i32.load8_u (i32.add (local.get $ptr) (local.get $i))) (i32.const 88))
          (then (return (i32.const 1))))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $l)))
    (i32.const 0)))
```

In practice you would write the rule in Rust, Zig or AssemblyScript and compile to `wasm32-unknown-unknown` with no imports.

## Upload and manage (admins)

```bash
curl -X POST https://your-gateway/api/v1/policy-plugins \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d "{\"name\": \"no-codenames\", \"module_b64\": \"$(base64 -w0 plugin.wasm)\"}"
```

| Method | Path | |
|---|---|---|
| `GET` | `/api/v1/policy-plugins` | List: name, SHA-256, size, enabled. |
| `POST` | `/api/v1/policy-plugins` | Upload (`name`, `module_b64`, `enabled`). The module is checked against the contract and given a test call before it is stored. 422 `invalid_plugin` says why it was refused. |
| `PATCH` | `/api/v1/policy-plugins/{id}` | `{"enabled": true\|false}`. Takes effect immediately. |
| `DELETE` | `/api/v1/policy-plugins/{id}` | Remove it. |

Up to 5 plugins per organization, 1 MB each, with names of lowercase letters, digits, `-` and `_`. Every upload, enable, disable and delete is in the admin audit log with the module's SHA-256. A request a plugin blocks is a normal policy refusal (HTTP 446) with `reason_code` `wasm_plugin:<name>`, or `wasm_plugin_error:<name>` when the plugin failed.

The list of enabled plugins can be changed only through these endpoints: the policy endpoint ignores a `wasm_plugins` field, so a plugin cannot be added without passing the upload checks.
