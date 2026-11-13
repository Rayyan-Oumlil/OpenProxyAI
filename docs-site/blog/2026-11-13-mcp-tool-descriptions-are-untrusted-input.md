---
slug: mcp-tool-descriptions-are-untrusted-input
title: "An MCP tool description is untrusted input, and so is its output"
tags: [security, engineering]
description: Agents read tool descriptions as instructions and act on tool results. Both can be changed by whoever runs the server. Here are the four controls an MCP gateway needs, and what each one cannot catch.
---

When an agent connects to an MCP server it receives a list of tools, each with a name and a description written in natural language. The model reads those descriptions the way it reads a prompt. If the server's owner changes a description tomorrow, the model's behavior changes with it, and nothing in your code review ever saw the change.

{/* truncate */}

## The three ways a tool turns on you

- **It changes after you approved it.** The description you reviewed on Monday is not the one served on Friday.
- **It carries instructions.** Text like "ignore previous instructions", hidden zero-width characters, or "do not tell the user" inside a description or a result.
- **It is trusted with too much.** A tool that reads a web page and a tool that sends email sit in the same session. Output from the first can steer the second.

## The four controls

**1. Pinning.** The gateway hashes each tool definition (SHA-256 of canonical JSON) and keeps every version. In `warn` mode the first definition is trusted and later changes mark the tool `drifted`. In `enforce` mode an admin must approve a change, and the agent is served the approved snapshot, never the live description. A drifted tool is hidden and refused until someone looks at it.

**2. Scanning.** Descriptions and every tool result are checked for invisible Unicode, instruction-override phrases, concealment wording, markdown-image exfiltration URLs, long base64 runs and oversized or deeply nested text. Each server chooses `log`, `redact` or `block`. The default is `log`, because these are heuristics and they will false-positive; a block that fires wrongly stops real work.

**3. Grants.** Who may call which tool is a rule set (by role, team, user or key, with patterns over `server__tool`). A deny always wins. An agent can narrow its own tool list with a header but never widen it.

**4. Taint tracking.** A session is marked tainted when any tool outside your trusted list returns output. A tool you labeled as a sink (one with side effects) then refuses to run in that session. The same rule applies on the chat path: if the conversation contains untrusted tool output, sink tools are removed from the request.

## What it cannot catch

- **Scanning is pattern matching.** A well-phrased injection that avoids the known patterns passes. Treat scanning as a tripwire, and treat pinning and taint tracking as the real boundary.
- **Taint is coarse.** It marks a whole session, so it will block some harmless sequences. That is the price of being predictable.
- **It only governs traffic through it.** An agent with a direct connection to the server skips all four.

## What gets recorded

Every `tools/call` is one audit row with the tool, the outcome and, for blocks, the reason code and the category of finding (never the text itself), so a SIEM can alert on `AI-TOOL-DRIFT` or `AI-TAINT-BLOCK` without holding anyone's prompts.
