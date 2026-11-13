---
slug: data-class-taxonomy-people-use
title: "Designing a data-class scheme that people will actually use"
tags: [architecture, security]
description: Four ordered data classes, a detector that can only raise them, and a model registry that compares ranks. How the scheme works in a gateway, with a worked example and the places it cannot be trusted.
---

Most data-classification schemes die in a spreadsheet. They have eleven labels, three owners, and nobody can say which label a support ticket gets. A gateway needs the opposite: a scale small enough that a developer picks the right label in a second, and ordered enough that a machine can compare two labels without a lookup table. OpenProxyAI uses exactly four classes, and this post explains why that works and where it stops working.

{/* truncate */}

![A ladder of four data classes, public to secret, with example data on each rung and the models allowed to see each class](/img/blog/data-class-taxonomy-people-use.svg)

## Why a short ordered scale beats many labels

The four classes are `public`, `internal`, `confidential` and `secret`, from least to most sensitive. In the code they are a fixed list, and each class has a rank from 0 to 3 (`backend/app/services/data_class.py`). Asking for the rank of anything else raises an error. The comment on that function says why: never guess a class.

That one design choice buys three things.

- **Comparison is a number check.** "May this model see this request" becomes "is the model's rank at least the request's rank". No policy language is needed.
- **Mistakes are one step wide.** If someone labels data `internal` that should be `confidential`, the error is one rung, not a category that does not exist.
- **People can remember it.** Four words fit in a header value and in a form field.

The cost is coarseness. Four classes cannot express "health data, but only for the claims team". That belongs in the policy allowlist and team rules, not in the scale. Keep the scale about sensitivity and let other controls handle who and where.

## How a class gets attached to a request

The effective class of a request is the highest of three inputs (`backend/app/services/classification_service.py`):

1. The organization's default class (`default_data_class`, which is `internal` unless changed).
2. The class a caller asserts in the `X-OpenProxy-Data-Class` header.
3. The class of each kind of personal data the detector finds, looked up in a class map.

The rule is a `max` over those candidates. So a caller can raise a request to `confidential` with the header, but cannot lower one that the default or the detector already put there. A header value that is not one of the four names raises an error instead of being ignored, so a typo does not silently mean "no claim".

This has a consequence worth designing around. The organization default is a floor. If you set it to `internal`, no request is ever classified `public`, because nothing can go below the floor. Pick the default as "what should an unlabeled request be treated as", and have callers raise from there.

The built-in detector (`backend/app/services/pii_detection.py`) finds three kinds of value: email addresses, US Social Security numbers, and payment card numbers. The default class map sends emails to `internal`, and SSNs and payment cards to `confidential`. An organization can override the map per kind. When the optional Presidio engine is installed, it replaces the built-in detector and adds more kinds, such as names, phone numbers and IBANs, each with a default class in the same map.

Blocked keywords are a separate feature. They refuse a request. They do not assign a class.

## How a class is used

Classification only describes a request. Routing acts on it (`backend/app/services/routing_service.py`). With `routing_mode` set to `enforce`, a model serves a request only if it passes every check, and each exclusion carries a reason:

| Check | Reason code if it fails |
|---|---|
| Model is enabled in the registry | `disabled` |
| A provider key is linked and active | `no_key`, `key_inactive` |
| Clearance is at least the request class | `class_too_low` |
| Model is available in the org's region | `region` |
| Model risk rating is within the org maximum | `risk` |
| Model is on the policy allowlist | `not_allowed_by_policy` |

Clearance is the lower of two numbers: the model's own `max_data_class` in the registry, and the `max_data_class` of the provider key that serves it. The reason for taking the lower is in the module docstring: a key's class can be lowered after the model was registered. The registry API also refuses to clear a model above its key.

A refused request is not swapped to another model. The caller gets a plain-language explanation. See [Provider routing](/core-concepts/provider-routing) and [Policies and guardrails](/core-concepts/policies-and-guardrails).

There is a second ceiling for things the registry does not govern: the semantic cache's embedding endpoint, and the evaluation hook or judge model. `OFF_REGISTRY_MAX_DATA_CLASS` (default `internal`) sets the highest class allowed to reach them. Above it, an enforcing organization skips the semantic cache and the evaluation. See [Environment flags](/getting-started/environment-flags) and the related post on [the semantic cache as shared memory](/blog/semantic-cache-is-shared-memory).

## What unclassifiable input does

Some input cannot be read. Audio is the clear case, and so are images, files, and any input part the gateway does not recognise. Text that is too large to scan also counts. These requests are classified as uninspected, and the default class map sends that to `confidential`. An organization can change the mapping for it, which is why the docs say "confidential unless the class map says otherwise". The same applies to realtime audio sessions.

Treating the unreadable as sensitive is the safe default: not knowing is not evidence of harmlessness.

## A worked example (hypothetical)

Take a made-up regional insurer. It sets its organization default to `internal` and routing to `enforce`. Its registry has three models, also made up for this example.

| Data | How it gets its class | Class | Models that may see it |
|---|---|---|---|
| Public product brochure text, rewritten for a web page | The default is the floor, so the app sends no header and gets `internal` | `internal` | Any model cleared for `internal` or higher |
| Staff email addresses in a meeting summary | Detector finds `email`, map says `internal` | `internal` | Same |
| A claim note with a customer's card number | Detector finds `payment_card`, map says `confidential` | `confidential` | Only models whose registry class and key class are both `confidential` or higher |
| Draft merger documents | No detector finds this. The calling app sends `X-OpenProxy-Data-Class: secret` | `secret` | Only a self-hosted model whose key is cleared for `secret` |
| A voice memo sent for transcription | Audio is uninspected | `confidential` | Same as the claim note |

Two lessons from the table. First, the insurer wanted brochure text to reach a cheap public model, but the floor prevents it. If that matters, it needs a different organization or a lower default. Second, the `secret` row only works because the application sets the header. Nothing in the detector knows what a merger is.

## What this does not do

- **The detector is a gate, not a guarantee.** The built-in one finds only email addresses, formatted US SSNs, and Luhn-valid card numbers. Its own docstring lists what it deliberately skips: nine bare digits, spelled-out addresses like `jane [at] example`, and phone numbers. It has no notion of names, medical terms, source code, API keys, or non-US identifiers.
- **`secret` is never assigned by the default map.** It comes from the organization default, the header, or a custom map entry.
- **Classes only bind when routing is `enforce`.** In `log_only` mode the decision is recorded but nothing is refused, and the off-registry ceiling is not applied.
- **A caller can raise but not lower, which also means an honest caller must remember to raise.** A forgotten header on sensitive free text is only caught if the detector recognises something in it.
- **If PII detection is turned off for the org, the detector returns nothing**, so only the default and the header decide.
- **Templates are not certifications.** The compliance templates are starting configurations you apply and own.

## What to do now

- Decide your organization default as "how to treat an unlabeled request". Do not set it lower than you can defend.
- List the data your teams really send, and map each item to one rung before touching any settings.
- Give every model in the registry and every provider key a class on purpose. The lower of the two wins.
- Add custom entries to the class map for the kinds you care about, and have applications send the header for data no detector can see.
- Run the policy preview with a hypothetical request before turning on `enforce`.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

Needs Docker and no provider key. The console is at http://localhost:5173.

## Sources

- `backend/app/services/data_class.py`: the four classes and their ranks.
- `backend/app/services/classification_service.py`: the `max` rule, the header, the default class map, the uninspected entry.
- `backend/app/services/pii_detection.py`: what the built-in detector finds and deliberately skips.
- `backend/app/services/routing_service.py`: clearance, exclusion reasons, the off-registry rule.
- [Policies and guardrails](/core-concepts/policies-and-guardrails), [Provider routing](/core-concepts/provider-routing), [Environment flags](/getting-started/environment-flags), [Data residency](/guides/data-residency): product documentation.
- [Semantic cache is shared memory](/blog/semantic-cache-is-shared-memory): why the cache sits outside the registry.

These statements are based on the OpenProxyAI source and docs read on November 13, 2026. The insurer is a hypothetical example.
