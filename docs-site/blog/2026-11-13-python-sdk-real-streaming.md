---
slug: python-sdk-real-streaming
title: "What broke when our Python SDK met a real streaming connection"
tags: [engineering]
description: Our Python SDK streaming passed its tests and failed on a live model. Why mocked responses hid two bugs, the exact code before and after, and what SDK authors should test against a real connection.
---

Our Python SDK had streaming tests and they passed. Then we pointed the SDK at a live model through the gateway and `stream=True` failed with an httpx `StreamClosed` error. The async client was no better: it returned the first chunk and stopped. Neither bug could show up in a test that never opened a real connection. This post shows what went wrong, the fix, and what we now test.

{/* truncate */}

![Two panels. Top: a mocked response is a body already in memory, readable twice, nothing to close. Bottom: a real connection is open and delivers chunks over time, one reader, one pass; closing it early gives StreamClosed.](/img/blog/python-sdk-real-streaming.svg)

## The problem

A streamed chat completion is not a value. It is an open HTTP connection that delivers server-sent events (lines starting with `data:`) over time. Whoever opens it owns it. They must read it once, in order, and close it.

A mocked response is a value. In our tests the response was built like this:

```python
respx.post(URL).mock(return_value=httpx.Response(200, content=SSE.encode(), headers={"x-openproxyai-request-id": "req-1"}))
```

`content=SSE.encode()` is the entire body as bytes, in memory, before the SDK asks for anything. There is no socket to close and no position to lose. Code that closes the response too early, or asks for a fresh line iterator on every step, can get away with it.

## Why the old tests could not see it

Before this fix, the streaming test file imported two helpers, `_parse_chunk` and `_extract_gateway_meta`, and tested those. They are pure functions: a line goes in, a chunk comes out. That is useful, and it never touched the code that opens, reads and closes the connection. Nothing in the file exercised `_stream` at all.

The lesson is not "mocks are bad". A mock tests the logic you wrote against the world you imagined. The two bugs lived in the gap between the two.

## Bug 1: the sync client lost its connection

The old sync client entered httpx's `stream()` context manager by hand and handed the response to the stream object:

```python
response = self._http.stream("POST", path, json=json_body)
# Enter the context manager to get the actual response
ctx = response.__enter__()
return SyncStream(ctx)
```

The context manager object itself was dropped. As the fix comment says, dropping it lets the garbage collector close the connection while we are still iterating. On a real connection the next read raised `StreamClosed`.

The fix builds the request and sends it with `stream=True`, which returns an open response that our stream object owns:

```python
request = self._http.build_request("POST", path, json=json_body)
response = self._http.send(request, stream=True)
if response.status_code >= 400:
    try:
        response.read()
        _raise_for_status(response)
    finally:
        response.close()
return SyncStream(response)
```

Two details matter. For a status of 400 or above, we read the body so the typed error can be built from it, then close in `finally`. And the stream object now closes the response when iteration ends, however it ends:

```python
try:
    for line in self._response.iter_lines():
        ...
finally:
    self._response.close()
```

## Bug 2: the async stream made a new iterator per chunk

The async stream's `__anext__` started a new `aiter_lines()` on every call, returned the first parsed chunk, and abandoned the iterator. The code comment in the fix states the rule: httpx refuses a second `aiter_lines()` on a response that is already being read. The result for users was a stream that stopped after one chunk.

The fix holds one line iterator for the life of the stream and closes the response when it runs dry:

```python
self._lines = response.aiter_lines()
...
async for line in self._lines:
    ...
await self._response.aclose()
raise StopAsyncIteration
```

The async client got the same `build_request` plus `send(stream=True)` treatment as the sync one, with `aread()` and `aclose()`.

## A side effect: refusals now arrive as typed errors

Reading the body before raising gives a policy refusal on a streamed request the same typed error as on a normal one, before any chunk is yielded. The test sends a 446 response with `reason_code` and `explanation` and expects `PolicyViolationError` with the explanation intact. For why the explanation exists, see [refusals should explain themselves](/blog/refusals-should-explain-themselves).

## How we found it, and what we added

We found it by running the SDK against a real local model (Ollama) through the demo gateway. That is the whole method: a real model, a real connection, the real client.

Then we added four regression tests in `sdk/python/tests/test_streaming.py`:

| Test | What it pins down |
|---|---|
| sync stream yields every chunk and closes | All chunks arrive, `stream._response.is_closed` is true afterwards |
| sync stream refusal | Typed error raised before any chunk |
| async stream yields every chunk, not just the first | The text joins to `Hello` |
| async stream refusal | Typed error raised |

We ran them against the old code to make sure they fail there, and they do.

## What this does not do

- The new tests still use `respx` mocks. They assert the things the bugs broke (every chunk, closed afterwards, error before the first chunk), but they are not a live-connection test. The live run was done by hand against Ollama. The SDK's test suite has no automated test that streams from a real server.
- We checked the Python SDK only. This post says nothing about the TypeScript SDK.
- Closing in `finally` covers normal ends and exceptions. We did not test what happens when a caller abandons a stream object without iterating it or leaving its `with` block.

## For SDK authors

- Test the function that opens, reads and closes the connection, not only the parser.
- Run at least one real streamed call against a real server before release. Count the chunks and check the connection is closed afterwards.
- Decide who owns the response. If your stream object returns it to a caller, do not leave a context manager behind that can close it.
- Create the line iterator once.
- Read the body of an error response before raising, so the error carries the server's reason.
- Test the refusal path on streams. It is a different code path from success.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173.

## Sources

- Commit `2246949` in the OpenProxyAI repository: the SDK changes in `sdk/python/src/openproxy/_client.py`, `_async_client.py` and `_streaming.py`, and the tests in `sdk/python/tests/test_streaming.py`.
- [Errors and status codes](/api-reference/errors-and-status-codes): the gateway's error format, including policy refusals.
- [Refusals should explain themselves](/blog/refusals-should-explain-themselves): why a refusal carries an explanation.
- The "Fixed (Python SDK)" entry in the November 2026 changelog (`docs-site/docs/changelog.md`).

These statements are based on the repository code, tests and commit message as of 2026-11-13.
