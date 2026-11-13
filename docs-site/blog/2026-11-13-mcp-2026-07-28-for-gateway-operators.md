---
slug: mcp-2026-07-28-for-gateway-operators
title: "MCP 2026-07-28 removes the session. What that changes for a gateway in the middle"
tags: [security, architecture]
description: The new MCP spec drops the initialize handshake and the session id, and adds headers a gateway can route on. That is good for scaling and removes the thing some gateway controls were built on. What changes, what to test, and where our own gateway stands.
---

The MCP specification dated 2026-07-28 is the largest revision since the protocol launched, according to its maintainers. The headline change is a stateless core: the `initialize` handshake and the `Mcp-Session-Id` header are gone. For a server author that is simpler. For anything sitting between an agent and its tools, it moves the ground under features that assumed a session existed. This post is about the gateway's point of view, including where ours stands today.

{/* truncate */}

![Two diagrams side by side. On the left, 2025-11-25: an agent talks to a gateway and then a tool server, with a session id on every call. On the right, 2026-07-28: the same path with no handshake and no session id, and Mcp-Method and Mcp-Name headers instead.](/img/blog/mcp-stateless.svg)

## What changed, from the maintainers' release post

- **No handshake, no session.** Each request carries its own protocol version, client identity and capabilities in `_meta`. A new `server/discover` call is optional. Any request can land on any server instance behind a plain round-robin load balancer. If a server needs state across calls, the post suggests minting an explicit handle from a tool and having the model pass it back as an argument.
- **Routing headers.** Streamable HTTP requests must now include `Mcp-Method` and `Mcp-Name`, so a gateway, rate limiter or WAF can route and meter without parsing the JSON body.
- **Multi round-trip requests.** Server-to-client requests such as sampling and elicitation no longer need a held-open stream. A server returns `input_required` with the questions, and the client retries the call with the answers attached.
- **Cacheable lists.** `tools/list` and similar responses carry `ttlMs` and `cacheScope`.
- **Authorization hardening.** Issuer validation per RFC 9207, credentials bound to the issuer that minted them, and a formal move from Dynamic Client Registration (now deprecated) to Client ID Metadata Documents.
- **Extensions and deprecations.** Tasks move into an extension. Roots, Sampling and Logging are deprecated, along with the legacy HTTP+SSE transport, with at least twelve months of notice under a new deprecation policy.

## What it means in the middle

Most of this helps a gateway. Header routing means policy decisions no longer require buffering and parsing every body. Statelessness means a gateway can scale horizontally without shared session storage. But each change also opens a question that a careful operator should test rather than assume.

These are our reading of the spec as a gateway author, not statements from the spec itself.

1. **A header is a claim, not a fact.** If a gateway authorizes on `Mcp-Name: search` but forwards a body whose `params.name` is `delete_repo`, the check passed on the wrong thing. Whatever you authorize on, the header and the body must agree, and a mismatch should be refused, not resolved in favor of one.
2. **Cache hints can outlive an approval.** A `ttlMs` on a tool list is a statement by the server about how long the list is valid. If your gateway approves tools and pins their definitions, a cached list must never keep a tool visible after you blocked it or after its definition changed.
3. **Multi round-trip requests are a new input path.** The answers a client attaches on the retry are text that reaches the tool. They need the same scanning and policy checks as the original arguments.
4. **A stateless protocol still has state, just not in the transport.** Anything that tracked what an agent had already done in a session now has to track it somewhere else, or stop tracking it.

## Where OpenProxyAI stands

Be clear about the version first. **Our MCP gateway speaks protocol 2025-11-25, and accepts 2025-06-18 and 2025-03-26 clients. It does not implement 2026-07-28 today.** It supports `initialize`, `ping`, `tools/list` and `tools/call`; resources and prompts are not proxied.

Which of our controls depend on the session, and which do not:

| Control | Needs a session? |
|---|---|
| Tool pinning and drift detection (hash of the whole tool definition, `warn` or `enforce`) | No. It works from the definitions the server advertises. |
| Injection scanning of descriptions and results | No. |
| Allow and deny grants, request scope, and bundles | No. Evaluated on each call. |
| Organization allow and block lists, argument guardrails, per-key rate limits | No. |
| **Taint tracking for tools with side effects** | **Yes.** |

Taint tracking works like this. A result from a tool that is not marked trusted taints the session. A tool marked as a sink, one with side effects such as send or delete, refuses to run in a tainted session, or with no session at all, so a client cannot drop its session id to launder the taint away. The same bookkeeping lives in a session bound to the API key that opened it.

Remove the session and that design needs an answer. The release post's own suggestion, an explicit handle that the model passes between tools, moves the state somewhere the model can see and the gateway cannot always check. Whatever replaces it has to keep the property that matters: a sink must not run on the strength of content that an untrusted tool just returned, and a client must not be able to opt out by omitting something. We have not shipped a design for that. We would rather say so than imply that stateless support is a version bump.

![The OpenProxyAI MCP servers page showing a server with pinning set to Enforce and injection scan set to Redact, with columns for upstream auth, status and when it was added.](/img/blog/console-mcp-servers.png)

## What to do now

If you operate or use an MCP gateway:

- **Ask which spec version it speaks, and what it does with a request from a newer client.** Many clients and SDKs have already moved. Know whether you get an error, a silent downgrade or a bypass.
- **Inventory what depends on the session.** Rate limits, audit grouping, taint tracking, anything that says "per session".
- **Write tests for header and body disagreement** before you start routing on headers.
- **Check cache behavior against your approvals.** Block a tool, then confirm that no cached list still serves it.
- **Plan for the deprecations.** Roots, Sampling, Logging and HTTP+SSE have at least twelve months. Dynamic Client Registration is deprecated and will be removed from a future version.

## Try the controls that exist today

OpenProxyAI is open source (Apache-2.0). The demo runs with Docker, needs no provider key, and comes with an MCP server already registered with pinning on enforce and scanning on redact, so you can see where those settings live in the console. The server in the demo is a placeholder address, so to watch a real tool go from pending to approved, register your own.

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

The [MCP gateway guide](/guides/mcp-gateway) covers pinning, scanning, grants, bundles and trust rules, and the [MCP admin API](/api-reference/mcp-admin) lists every endpoint.

## Sources

- [Model Context Protocol blog: The 2026-07-28 specification](https://blog.modelcontextprotocol.io/posts/2026-07-28/), the release post (stateless core, headers, MRTR, caching, authorization, deprecations).
- [Model Context Protocol blog: 2026-07-28 release candidate](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/), the earlier candidate announcement.
- OpenProxyAI docs: [MCP gateway](/guides/mcp-gateway), [MCP admin API](/api-reference/mcp-admin).

Spec details are from the maintainers' release post as of November 13, 2026. Read the specification itself before you build against a detail. Statements about our gateway come from its current documentation and code.
