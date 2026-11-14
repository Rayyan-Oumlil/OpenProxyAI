---
slug: mcp-2026-07-28-for-gateway-operators
title: "MCP 2026-07-28 removes the session. What that changes for a gateway in the middle"
tags: [security, architecture]
description: The new MCP spec drops the initialize handshake and the session id, and adds headers a gateway can route on. What changes for anything between an agent and its tools, and a checklist for operators.
---

The MCP specification dated 2026-07-28 is the largest revision since the protocol launched, according to its maintainers. The headline change is a stateless core: the `initialize` handshake and the `Mcp-Session-Id` header are gone. For a server author that is simpler. For anything sitting between an agent and its tools, it moves the ground under features that assumed a session existed. This post is about the gateway's point of view.

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

Most of this helps a gateway. Header routing means policy decisions no longer require buffering and parsing every body. Statelessness means a gateway can scale horizontally without shared session storage. Each change also opens a question that a careful operator should test rather than assume. These are our reading of the spec as gateway authors, not statements from the spec itself.

1. **A header is a claim, not a fact.** If a gateway authorizes on `Mcp-Name: search` but forwards a body whose `params.name` is `delete_repo`, the check passed on the wrong thing. Whatever you authorize on, the header and the body must agree, and a mismatch should be refused, not resolved in favor of one.
2. **Cache hints can outlive an approval.** A `ttlMs` on a tool list is a statement by the server about how long the list is valid. If your gateway approves tools and pins their definitions, a cached list must never keep a tool visible after you blocked it or after its definition changed.
3. **Multi round-trip requests are a new input path.** The answers a client attaches on the retry are text that reaches the tool. They need the same scanning and policy checks as the original arguments.
4. **A stateless protocol still has state, just not in the transport.** Anything that tracked what an agent had already done in a session now has to track it somewhere else, or stop tracking it. A rule such as "do not run a side-effecting tool after an untrusted tool returned output" needs a new place to live.

## Controls that do not depend on a session

Some gateway controls evaluate each call on its own, so they are a natural fit for a stateless protocol:

| Control | Per call or per session |
|---|---|
| Tool pinning and drift detection | Per call, from the definitions the server advertises |
| Injection scanning of descriptions and results | Per call |
| Allow and deny grants, request scope, bundles | Per call |
| Organization allow and block lists, argument guardrails, rate limits | Per call |

The controls that track what happened earlier in a conversation are the ones to look at closely as the ecosystem moves, which is why the checklist below starts with an inventory.

![The OpenProxyAI MCP servers page showing a server with pinning set to Enforce and injection scan set to Redact, with columns for upstream auth, status and when it was added.](/img/blog/console-mcp-servers.png)

## What to do now

If you operate or use an MCP gateway:

- **Ask which spec version it speaks, and what it does with a request from a newer client.** Many clients and SDKs have already moved. Know whether you get an error, a silent downgrade or a bypass.
- **Inventory what depends on the session.** Rate limits, audit grouping, anything that says "per session".
- **Write tests for header and body disagreement** before you start routing on headers.
- **Check cache behavior against your approvals.** Block a tool, then confirm that no cached list still serves it.
- **Plan for the deprecations.** Roots, Sampling, Logging and HTTP+SSE have at least twelve months. Dynamic Client Registration is deprecated and will be removed from a future version.

## Try it

OpenProxyAI is open source (Apache-2.0). The demo includes an MCP server already registered with pinning on enforce and scanning on redact, so you can see where those settings live in the console.

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker and no provider key. The console is at http://localhost:5173. The [MCP gateway guide](/guides/mcp-gateway) covers pinning, scanning, grants, bundles and trust rules, and the [MCP admin API](/api-reference/mcp-admin) lists every endpoint. If it is useful, star the repo or open an issue.

## Sources

- [Model Context Protocol blog: The 2026-07-28 specification](https://blog.modelcontextprotocol.io/posts/2026-07-28/), the release post (stateless core, headers, MRTR, caching, authorization, deprecations).
- [Model Context Protocol blog: 2026-07-28 release candidate](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/), the earlier candidate announcement.
- OpenProxyAI docs: [MCP gateway](/guides/mcp-gateway), [MCP admin API](/api-reference/mcp-admin).

Spec details are from the maintainers' release post as of November 13, 2026. Read the specification itself before you build against a detail. These statements are based on OpenProxyAI's behavior at the post date.
