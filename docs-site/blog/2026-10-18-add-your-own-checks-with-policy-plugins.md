---
slug: add-your-own-checks-with-policy-plugins
title: "Add your own checks to the gateway with sandboxed policy plugins"
tags: [security, product]
description: "Block project codenames, internal ticket formats or any rule only your company knows. Write a small WebAssembly module, upload it, and it runs on every request in a sandbox that can only add restrictions."
---

Built-in policy covers what most companies need: which models are allowed, keywords, personal data and prompt injection. Then a security lead says, "We also never want our acquisition codenames to leave the building," or "Block anything that looks like a customer account number in our format." No product ships that rule, because only you know it. Policy plugins let you add it yourself, without waiting for a release and without giving untrusted code any power over the gateway.

{/* truncate */}

![A request passes the built-in policy checks first. If they allow it, the organization's plugin is asked. A plugin can only block, never lift a block. A refusal comes back as a normal policy block.](/img/blog/add-your-own-checks-with-policy-plugins.svg)

## What a plugin is

A plugin is a small program, packaged as WebAssembly, that reads the text of a request and answers one question: allow or block. WebAssembly is a compact format that many languages can compile to, and it is designed to run inside a strict sandbox. You write the rule in a language you already use, compile it, and upload it.

The plugin runs on chat and on every other endpoint, because they all share the same policy check. You do not wire it into each application.

## It can only add restrictions

This is the property that makes plugins safe to adopt.

- The built-in rules run first. The plugin is asked only about requests they allowed.
- A plugin can say block. It can never lift a block that another rule made.
- It follows the policy mode. In log-only mode a hit is recorded and not enforced, so you can try a new rule on live traffic first. In enforce mode a hit refuses the request. When policy is off, plugins are not asked.

That matches the rollout pattern most teams already use: watch in log-only, check the hits, then enforce. See [rolling out guardrails without breaking teams](/blog/roll-out-guardrails-without-breaking-teams).

## A sandbox built for code you do not trust

You may get a plugin from another team, a contractor or a vendor. The design assumes the worst case, which is that it fails.

| Guarantee | What it means for you |
|---|---|
| No access to anything | The module cannot read files, use the network, check the clock or call out. A module that asks for any of that is refused at upload. |
| Bounded time | A plugin that loops forever is stopped. |
| Bounded memory | A plugin cannot grow without limit. |
| No memory between calls | Every call starts fresh, so a plugin cannot remember one request for the next. |
| It sees the whole request | A request that is too large to judge in full is refused, not cut, so a plugin never rules on half a message. |
| Fails closed | If a plugin crashes, runs out of time, or its stored file no longer matches the fingerprint in your policy, the request is blocked under enforce, and the failure is recorded. It is never skipped. |

The last row is the important one. A broken plugin does not become a hole. It becomes a visible, logged block that someone can fix.

## Managing plugins

Admins manage plugins through the API. Each upload is checked against the plugin contract and given a test call before it is stored, and a refusal tells you why. You can list plugins, enable or disable one, and delete one, and a change takes effect immediately. Disabling is a fast way to take a rule out if it blocks something it should not.

Every upload, enable, disable and delete lands in the admin audit log together with the fingerprint of the module. Months later you can answer which exact version of a rule was active on a given day.

The list of enabled plugins can be changed only through the plugin endpoints. It cannot be added by editing policy, so nothing gets in without passing the upload checks.

## What the caller sees

A request that a plugin blocks is an ordinary policy refusal. It uses the same HTTP status as other policy blocks, 446, and the reason is labeled with the plugin's name. A plugin that failed is labeled as a plugin error. The caller gets the same plain refusal as for any other rule, and your dashboards, audit log and security events count it like any other policy block. See [an audit trail your auditor can read](/blog/an-audit-trail-your-auditor-can-read).

## A worked scenario

A company is preparing an acquisition and gives the deal a codename. Legal wants to be sure it never appears in a prompt.

1. A developer writes a short plugin that blocks any text containing the codename and its variants, and compiles it.
2. An admin uploads it. The upload check runs a test call and accepts it.
3. Policy is already in log-only mode, so the plugin starts by recording hits. For a week, the audit log shows two hits: both in a draft summary that someone pasted into a chat tool. Nothing was blocked.
4. The security lead decides the rule is right and moves policy to enforce.
5. A week later a third request containing the codename is refused with a plain message, the caller knows why, and the event appears in the audit log with the plugin's name.
6. When the deal closes, an admin disables the plugin. The change is recorded.

The rule took an afternoon to write and needed no release from OpenProxyAI.

## What to do now

- [ ] Write down the rules only your company can define: codenames, internal identifiers, customer formats.
- [ ] Start with the narrowest rule, and try it in log-only mode.
- [ ] Keep each plugin small and single-purpose, so a hit is easy to explain.
- [ ] Review plugin hits in the audit log before moving to enforce.
- [ ] Treat uploads like deployments: name them clearly and record who approved them.

## Good to know

A plugin judges the text of the request, so a rule that is too broad will block honest traffic. Keep patterns specific, and use log-only first. For common needs like personal data, the built-in detectors are the easier choice, and plugins are for what they cannot know.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

This needs Docker and no provider key. The console is at http://localhost:5173. If it helps you, star the repo, and if there is a plugin example you would like to see, open an issue.

## Sources

- [Policy plugins](/guides/policy-plugins): the contract, the sandbox guarantees, management endpoints and the refusal reason.
- [Policies and guardrails](/core-concepts/policies-and-guardrails): the built-in checks plugins sit behind.
- [Audit logging](/security/audit-logging): where plugin changes and blocks are recorded.
- [Roll out guardrails without breaking teams](/blog/roll-out-guardrails-without-breaking-teams): the log-only to enforce pattern.
- [Prompt injection defense in production](/blog/prompt-injection-defense-in-production): the built-in checks.

These statements are based on the sources above and on OpenProxyAI's behavior as of 2026-10-18.
