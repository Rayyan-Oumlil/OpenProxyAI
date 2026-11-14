---
slug: classification-markings-in-prompts
image: /img/blog/og/classification-markings-in-prompts.png
title: "Classification markings in prompts: keep what must not leave the boundary"
tags: [security, product]
description: "Documents carry markings such as Internal Use Only or Top Secret. Use blocked phrases and data classes to stop marked text at the gateway, avoid false positives, and roll the rules out in log-only first."
---

Most sensitive documents say so on the page. A footer reads "Internal use only". A header reads "Confidential". In some organizations the marking is a formal label with rules attached. Then someone pastes a paragraph into a chat prompt, and the marking travels with it to a model provider. The text already told you it should not go there. A gateway can listen. Here is how to turn markings into two controls: a hard stop for phrases that must never leave, and a data class that decides which models may see the rest.

{/* truncate */}

![A marked prompt enters the gateway. Blocked phrases refuse it with a 446. A raised data class limits which models may serve it. Everything else is served as normal.](/img/blog/classification-markings-in-prompts.svg)

## The problem

People do not paste documents to cause harm. They paste to summarize, translate or rewrite. The marking is the last thing on their mind. If your only control is a policy document that says "do not put classified material into AI tools", it depends on every person remembering it at every paste.

A gateway sits where the paste arrives. It can read the request text before any provider does, which makes markings a practical signal. They are not perfect, because unmarked text still exists. But a marking is the cheapest and clearest evidence you will ever get that a piece of text has rules attached.

## Two controls with different jobs

| Control | What it does | Use it for |
|---|---|---|
| Blocked phrases | Refuses the request with HTTP 446 when the text contains a phrase on your list | Markings that must never leave, whatever the model |
| Data classes | Gives the request a level (public, internal, confidential, secret) and lets routing choose only models cleared for that level | Material that may go to some models and not others |

**Blocked phrases.** The policy holds a list of phrases. Matching is case-insensitive and checks whether the phrase appears anywhere in the request text. The first match decides the outcome. In enforce mode the caller gets a 446 with a one-sentence explanation that does not reveal which phrase matched. If you also turn on response checks, a phrase in the model's answer is withheld in enforce mode.

**Data classes.** Every request gets one of four ordered levels. The level is the highest of the organization default, any level the caller asserts in a request header, and the level implied by personal data the detector finds. A caller can raise the level and never lower it. With routing in enforce mode, a model serves a request only if the model registry clears it for that level. If no cleared model exists, the request is refused. The gateway does not quietly swap in a different model. See [A data-class scheme that people will actually use](/blog/data-class-taxonomy-people-use).

## Which marking gets which control

Think in terms of consequences.

- **"Must not leave at all."** A formal marking such as a secret handling caveat. Put the exact marking on the blocked phrase list. No model sees it.
- **"May go to approved models only."** Internal or confidential material. Your application, which often knows the document's label, sends the matching data class with the request. Routing then limits it to models you cleared for that level. Personal data raises the level on its own.
- **"Anything else."** Served as normal.

The government compliance template already ships a marking list: classified, top secret, secret//noforn, controlled unclassified and fouo. It is a starting point, not a certification, and it replaces your keyword list when applied. See [Compliance templates](/security/compliance-templates).

## False positives are the real work

Phrase matching is simple, which is its strength and its risk. A word is not a marking.

| Phrase | Where it also appears | Better choice |
|---|---|---|
| classified | Classified ads, news summaries | The full caveat, such as secret//noforn |
| confidential | Every email disclaimer | A specific internal label, such as "confidential - client data" |
| secret | Secret Santa, secret manager, API secret fields | A longer phrase that only your labels use |
| internal use only | Often legitimate and wanted | Keep it, but expect hits on routine documents |

Short, common words fire constantly. Long, exact phrases fire when the marking is really there. Two habits help:

1. Prefer the exact string your document template prints, including punctuation.
2. Treat a rule that fires on most of your traffic as broken, not strict.

## Roll out in log-only first

Do not turn on a marking list in enforce mode and wait for complaints. The policy has a log-only mode where a hit is recorded and the request goes through.

1. Add the phrases while the policy is in log-only.
2. Let a full business cycle run, then open the policy activity and group hits by reason.
3. Export the events for a sample, open a few real rows, and see which team and which key sent them. The audit row shows the reason and the rule that fired, not the prompt text.
4. Tighten any phrase that fires on harmless text. Ask the teams behind real hits whether they were expected.
5. Use the policy preview to try a few made-up prompts, with and without the marking, and confirm the verdict.
6. Switch to enforce and watch the activity for another week.

The longer version of this plan is in [Roll out AI guardrails without breaking teams](/blog/roll-out-guardrails-without-breaking-teams).

## A worked scenario

A public-sector contractor handles documents with three kinds of markings.

| Marking on the document | Control | Result |
|---|---|---|
| A formal handling caveat | Exact phrase on the blocked list | Refused with a 446, no provider sees it |
| "Internal use only" | The writing tool sends the internal data class | Served only by models cleared for internal data |
| "Confidential - client data" | The writing tool sends the confidential data class | Served only by the models cleared for it, otherwise refused |

During the log-only week they find that "secret" fired on a developer tool's settings screen. They remove the single word and keep the longer caveat. Refusals then start with clean data behind them.

## What to do now

1. List the markings your organization actually prints, with their exact wording.
2. Split them into "must never leave" and "approved models only".
3. Put the first group on the blocked phrase list, in log-only mode.
4. Have your applications send a data class for documents that carry a label.
5. Review the policy activity after a full business cycle and fix noisy phrases.
6. Enforce, and make sure applications show the refusal sentence to users.

## Good to know

Phrase checks read the text of the request. Text inside a picture or a scanned page is not read that way, and audio is treated as uninspected input, which the default class map sends to confidential. A marking that nobody typed into the prompt cannot trigger a phrase rule, so pair phrases with data classes and with an approved model list. Enforcement is one mode for the whole policy, and this is a control you configure and run. Using it does not make an organization compliant with any framework.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. The demo already blocks one phrase, so you can see a 446 within minutes. If it helps, star the repo or open an issue.

## Sources

- OpenProxyAI docs: [Policies and guardrails](/core-concepts/policies-and-guardrails), [Compliance templates](/security/compliance-templates), [Provider routing](/core-concepts/provider-routing), [Data residency](/security/data-residency), [Managing your organization](/admin-console/managing-your-organization), [Chat completions](/api-reference/chat-completions).
- On this blog: [A data-class scheme that people will actually use](/blog/data-class-taxonomy-people-use), [Roll out AI guardrails without breaking teams](/blog/roll-out-guardrails-without-breaking-teams), [Compliance templates, not badges](/blog/compliance-templates-not-badges), [Refusals should explain themselves](/blog/refusals-should-explain-themselves).

These statements are based on OpenProxyAI's behavior and docs as of October 28, 2026.
