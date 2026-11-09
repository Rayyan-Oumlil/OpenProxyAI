# Demand signal without cold calls

Status: started 2026-11-09. Companion to `buyer-conversations.md`: that kit is for live calls; this is everything that
gets a real signal from public sources and from people who come to us, with no cold outreach.

**Rule:** a model pretending to be buyers (a "consumer panel") is brainstorming, not evidence. Only count what a real
person said or did: an issue they wrote, a comment, a star, a question, a call.

## What the first sweep found (2026-11-09)
| Signal | What it is | Strength |
|---|---|---|
| [LiteLLM #22966](https://github.com/BerriAI/litellm/issues/22966) | A user asked that a key scoped to an EU tag can never route to a non-EU deployment. The maintainers did not answer and it went stale. | One real person, a close match to our routing guarantee. Best lead. |
| LiteLLM [#46665](https://github.com/BerriAI/litellm/issues/46665), [#27293](https://github.com/BerriAI/litellm/issues/27293) | In-region routing and EU/US endpoint problems keep coming up. | Shows the pain recurs; these are bugs and small features. |
| Portkey and Kong issues | Guardrail-plugin requests; nothing on data classes. | Weak. |
| Vendor articles (NeuralTrust, Gravitee, C1.ai) | Route by data class is described as the pattern, and a failover that sends restricted data to an unapproved model is named as a risk. | Proves the idea exists. They are sellers, so this is not buyer proof. |
| EU AI Act logging | Deployers of high-risk systems keep logs at least six months (sources disagree on dates and scope; read Regulation 2024/1689 before quoting). | A real pressure for audit trails. |
| LiteLLM docs | Audit logs and SSO are in its paid tier; Kong's open source has PII redaction and audit logging. | Our free audit log is a differentiator; Kong already covers the basics. |

Not found: anyone asking to buy this. Reddit and Hacker News returned nothing useful through search.

## Tasks
| # | Task | Who | Status |
|---|---|---|---|
| D1 | This plan | me | done |
| D2 | Blog post on the sharpest claim: every fallback must come from the same authorized set (`docs-site/blog/2026-11-09-failover-can-leak-data.md`) | me | done, unpublished until merged |
| D3 | Issue template "I'd use this for..." so interested people have somewhere to land (`.github/ISSUE_TEMPLATE/`) | me | done |
| D4 | Comparison pages already exist (`docs-site/blog/*vs*`). Re-check their claims against current docs before sharing them | me | todo |
| D5 | Deeper public-issue sweep: Bifrost, Helicone, Langfuse, OpenRouter and more themes (audit logs behind a paywall, per-team model access, residency). The first attempt hit GitHub's secondary rate limit; run it slowly, with a pause between searches | me | todo |
| D6 | Drafts, not sent: a reply to the #22966 thread, a Show HN, a Reddit post, a LinkedIn post (kept out of the repo, because they name real people) | me | todo |
| D7 | Publish anything: comment on an issue, post anywhere, email anyone | **owner says yes first** | done for the items in the log; Hacker News, Reddit, LinkedIn and X are the owner's to paste |
| D8 | Hosted public demo (the biggest conversion lever; deployment is parked) | **owner** | parked |
| D9 | Turn on GitHub Discussions for the repo | **owner** (repo setting) | todo |

## Log (real signals and what was sent)
| Date | What | Link |
|---|---|---|
| 2026-11-09 | Merged the Apache-2.0 LICENSE (the repo was public with none) and the fallback-closure post; set the repo description and topics | #58, #59 |
| 2026-11-09 | Commented on the matching LiteLLM issue (public, from the owner's account, approved) | [comment](https://github.com/BerriAI/litellm/issues/22966#issuecomment-6748772669) |
| 2026-11-09 | Opened a PR adding OpenProxyAI to a large LLMOps list (approved) | [PR](https://github.com/tensorchord/Awesome-LLMOps/pull/1139) |
| 2026-11-09 | Six email drafts saved in Gmail with no recipients (no published addresses found); not sent | |
| | Held back on purpose: replies to unrelated LiteLLM threads (would read as spam), and a reply on audit-log paywalls (no matching thread found yet) | |

Real signals so far: none (no replies yet). Add each reply, star, issue or call here with a date.

## Rules
- Nothing is posted, commented or emailed without the owner's yes in that conversation, each time.
- Email only addresses a person or company published themselves. Never anyone at the owner's employer.
- Real people's names and contact details stay out of the repo. Link to the public thread instead.
- Count only real signals. Log them in this file with a date and a link.
