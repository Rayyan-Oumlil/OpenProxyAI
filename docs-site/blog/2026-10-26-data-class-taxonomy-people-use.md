---
slug: data-class-taxonomy-people-use
title: "Designing a data-class scheme that people will actually use"
tags: [architecture, security]
description: Four ordered data classes, a detector that can only raise them, and a model registry that compares ranks. How a short scale turns data sensitivity into routing decisions, with a worked example.
---

Most data-classification schemes die in a spreadsheet. They have eleven labels, three owners, and nobody can say which label a support ticket gets. A gateway needs the opposite: a scale small enough that a developer picks the right label in a second, and ordered enough that a machine can compare two labels without a lookup table. OpenProxyAI uses exactly four classes, and this post explains why that works.

{/* truncate */}

![A ladder of four data classes, public to secret, with example data on each rung and the models allowed to see each class](/img/blog/data-class-taxonomy-people-use.svg)

## Why a short ordered scale beats many labels

The four classes are `public`, `internal`, `confidential` and `secret`, from least to most sensitive. Each one has a rank, and anything that is not one of the four is rejected rather than guessed.

That one design choice buys three things.

- **Comparison is a number check.** "May this model see this request" becomes "is the model's clearance at least the request's class". No policy language is needed.
- **Mistakes are one step wide.** If someone labels data `internal` that should be `confidential`, the error is one rung, not a category that does not exist.
- **People can remember it.** Four words fit in a header value and in a form field.

The scale stays about sensitivity. Questions like "health data, but only for the claims team" belong in the policy allowlist and team rules, so each control does one job.

## How a class gets attached to a request

The effective class of a request is the highest of three inputs:

1. The organization's default class, which is `internal` unless you change it.
2. The class a caller asserts in the `X-OpenProxy-Data-Class` header.
3. The class of each kind of personal data the detector finds, looked up in a class map you can customize.

Because the result is the highest of the three, a caller can raise a request to `confidential` with the header, and nothing downstream can quietly lower it. A header value that is not one of the four names is refused, so a typo never silently means "no claim".

The organization default works as a floor. Pick it as "what should an unlabeled request be treated as", and have callers raise from there.

The built-in detector finds email addresses, US Social Security numbers and payment card numbers, and the default map sends emails to `internal` and the other two to `confidential`. Organizations can override the map per kind, and an optional detection engine adds more kinds such as names, phone numbers and IBANs.

## How a class is used

Classification describes a request. Routing acts on it. With routing in enforce mode, a model serves a request only if it passes every check, and each exclusion carries a reason you can read:

| Check | Reason if it fails |
|---|---|
| Model is enabled in the registry | `disabled` |
| A provider key is linked and active | `no_key`, `key_inactive` |
| Clearance is at least the request class | `class_too_low` |
| Model is available in the org's region | `region` |
| Model risk rating is within the org maximum | `risk` |
| Model is on the policy allowlist | `not_allowed_by_policy` |

Clearance is the lower of two values: the model's own class in the registry and the class of the provider key that serves it. So lowering a key's class takes effect right away, even for models registered earlier.

A refused request is not silently swapped to another model. The caller gets a plain-language explanation. See [Provider routing](/core-concepts/provider-routing) and [Policies and guardrails](/core-concepts/policies-and-guardrails).

## What unreadable input does

Audio, images, files and any input the gateway does not recognise cannot be scanned. These requests are classified as uninspected, and the default class map sends that to `confidential`. You can change the mapping, which is why the docs say "confidential unless the class map says otherwise". Treating the unreadable as sensitive is the safe default: not knowing is not evidence of harmlessness.

## A worked example (hypothetical)

Take a made-up regional insurer. It sets its organization default to `internal` and routing to enforce. Its registry has three models, also made up for this example.

| Data | How it gets its class | Class | Models that may see it |
|---|---|---|---|
| Product brochure text, rewritten for a web page | The default applies, no header needed | `internal` | Any model cleared for `internal` or higher |
| Staff email addresses in a meeting summary | Detector finds an email, map says `internal` | `internal` | Same |
| A claim note with a customer's card number | Detector finds a card number, map says `confidential` | `confidential` | Only models whose registry class and key class are both `confidential` or higher |
| Draft merger documents | The calling app sends `X-OpenProxy-Data-Class: secret` | `secret` | Only a self-hosted model whose key is cleared for `secret` |
| A voice memo sent for transcription | Audio is uninspected | `confidential` | Same as the claim note |

Two lessons from the table. The detector handles the data it knows about without any developer effort, and the header lets an application declare what no detector could know, such as what a merger is. Together they cover both automatic and deliberate classification.

## What to do now

- Decide your organization default as "how to treat an unlabeled request".
- List the data your teams really send, and map each item to one rung before touching any settings.
- Give every model in the registry and every provider key a class on purpose. The lower of the two wins.
- Add custom entries to the class map for the kinds you care about, and have applications send the header for data no detector can see.
- Run the policy preview with a hypothetical request before turning on enforce mode.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker, no provider key. Console at http://localhost:5173. If it saves you time, star the repo or open an issue with the data classes your team actually needs.

## Sources

- [Policies and guardrails](/core-concepts/policies-and-guardrails), [Provider routing](/core-concepts/provider-routing), [Environment flags](/getting-started/environment-flags), [Data residency](/security/data-residency): product documentation.
- [Semantic cache is shared memory](/blog/semantic-cache-is-shared-memory): why the cache sits outside the registry.

These statements are based on OpenProxyAI's behavior at the post date. The insurer is a hypothetical example.
