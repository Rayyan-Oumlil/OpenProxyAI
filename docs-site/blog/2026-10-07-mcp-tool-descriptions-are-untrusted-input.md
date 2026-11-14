---
slug: mcp-tool-descriptions-are-untrusted-input
title: "An MCP tool description is untrusted input, and so is its output"
tags: [security, engineering]
description: Agents read tool descriptions as instructions and act on tool results. Both can be changed by whoever runs the server. Here are four controls an MCP gateway should give you, and how OpenProxyAI approaches each.
---

When an agent connects to an MCP server it receives a list of tools, each with a name and a description written in natural language. The model reads those descriptions the way it reads a prompt. If the server's owner changes a description tomorrow, the model's behavior changes with it, and nothing in your code review ever saw the change.

{/* truncate */}

## The three ways a tool turns on you

- **It changes after you approved it.** The description you reviewed on Monday is not the one served on Friday.
- **It carries instructions.** Text like "ignore previous instructions", hidden zero-width characters, or "do not tell the user" inside a description or a result.
- **It is trusted with too much.** A tool that reads a web page and a tool that sends email sit in the same session. Output from the first can steer the second.

## The four controls

| Control | What it does for you |
|---|---|
| **Pinning** | Each tool definition is fingerprinted and every version is kept. A changed tool is flagged as drifted. In enforce mode an admin approves the change, and the agent only ever sees the approved snapshot, never the live description. |
| **Scanning** | Descriptions and tool results are checked for invisible characters, instruction-override phrases, concealment wording and exfiltration tricks. Each server chooses whether to log, redact or block. |
| **Grants** | Who may call which tool is a rule set by role, team, user or key. A deny always wins, and an agent can narrow its own tool list but never widen it. |
| **Taint tracking** | When an untrusted tool returns output, tools you have labeled as having side effects refuse to run for the rest of that session. |

Together they cover the three failure modes. Pinning handles change after approval. Scanning handles carried instructions. Grants and taint tracking limit how much a single tool can be trusted with.

## Choosing how strict to be

Scanning starts in log mode so you can see what it would catch on your own traffic before you let it block anything. When the findings look right, move a server to redact or block. Pinning works the same way: begin by warning on changes, then require approval for the servers that matter most.

## What gets recorded

Every tool call is one audit row with the tool, the outcome and, for blocks, the reason and the category of finding (never the text itself), so a SIEM can alert on tool drift or a taint block without holding anyone's prompts.

## Good to know

These controls apply to traffic that goes through the gateway, so point your agents at the gateway as their only route to MCP servers.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker and no provider key. The console is at http://localhost:5173, where the MCP servers page shows pinning and scanning settings. The [MCP gateway guide](/guides/mcp-gateway) covers each control in detail. If it helps, star the repo or open an issue.

These statements are based on OpenProxyAI's behavior at the post date.
