---
slug: python-sdk-real-streaming
title: "Real streaming in the Python SDK, token by token"
tags: [engineering]
description: How the OpenProxyAI Python SDK streams chat completions token by token, in both sync and async clients, and what SDK authors should test against a real connection.
---

Streaming is the feature users feel most. A model starts answering and the words appear as they are generated. The OpenProxyAI Python SDK supports it in both the sync and the async client: set `stream=True` and you receive every chunk, in order, as it arrives. This post explains what makes streaming different from an ordinary call, how the SDK handles it, and what we verify against a live model.

{/* truncate */}

![Two panels. Top: a mocked response is a body already in memory, readable twice, nothing to close. Bottom: a real connection is open and delivers chunks over time, one reader, one pass, owned by the stream object.](/img/blog/python-sdk-real-streaming.svg)

## A stream is a connection, not a value

A streamed chat completion is an open HTTP connection that delivers server-sent events (lines starting with `data:`) over time. Whoever opens it owns it. They read it once, in order, and close it.

That is different from a normal response, which is a value: the whole body is available at once, can be read twice, and has nothing to close. The two behave very differently, so a client that streams has to be designed around a connection that stays open.

## How the SDK handles it

Three principles shape the streaming clients.

- **The stream object owns the response.** When you call with `stream=True`, you get back a stream that holds the open connection until you are done with it.
- **One reader, one pass.** The stream reads the connection through a single iterator for its whole life, so every chunk arrives, not just the first one. This holds for the sync client and the async client alike.
- **It always closes.** When iteration ends, however it ends, the connection is closed. Leaving a `with` block does the same.

## Refusals arrive as typed errors

A policy refusal on a streamed request produces the same typed error as on a normal request, and it is raised before any chunk is yielded. The explanation travels with it, so your code can show the user why. For why the explanation exists, see [refusals should explain themselves](/blog/refusals-should-explain-themselves), and for the error format, see [Errors and status codes](/api-reference/errors-and-status-codes).

## How we verify it

Parsing logic can be tested with mocks, and we do. But a mock hands the client a body that is already in memory, with no socket to close and no position to lose. A real stream behaves differently, so the method we trust is simple: a real model, a real connection, the real client.

We run the SDK against a real local model through the demo gateway, count the chunks, and check that the connection is closed afterwards. Regression tests pin down the behaviors that matter:

| Check | What it pins down |
|---|---|
| Sync stream | Every chunk arrives and the connection is closed afterwards |
| Sync refusal | Typed error raised before any chunk |
| Async stream | Every chunk arrives, and the text joins into the full answer |
| Async refusal | Typed error raised |

## For SDK authors

- Test the code that opens, reads and closes the connection, not only the parser.
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

Needs Docker, no provider key. Console at http://localhost:5173. If you stream through the SDK, star the repo or open an issue and tell us how it goes.

## Sources

- [Errors and status codes](/api-reference/errors-and-status-codes): the gateway's error format, including policy refusals.
- [Refusals should explain themselves](/blog/refusals-should-explain-themselves): why a refusal carries an explanation.

These statements are based on OpenProxyAI's behavior at the post date.
