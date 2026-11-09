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
| LiteLLM docs | Audit logs and SSO beyond 5 users are in its paid tier. | Our audit log ships in the one thing you deploy; that is a differentiator. |
| Kong docs | The AI PII Sanitizer and AI Proxy Advanced are marked AI Gateway Enterprise only (checked 2026-11-09 against Kong's plugin pages). An earlier version of this row said Kong's open source has PII redaction; that was wrong. | Kong's PII and routing features are paid. |

Not found: anyone asking to buy this. Reddit and Hacker News returned nothing useful through search.

## Tasks
| # | Task | Who | Status |
|---|---|---|---|
| D1 | This plan | me | done |
| D2 | Blog post on the sharpest claim: every fallback must come from the same authorized set (`docs-site/blog/2026-11-09-failover-can-leak-data.md`) | me | done, unpublished until merged |
| D3 | Issue template "I'd use this for..." so interested people have somewhere to land (`.github/ISSUE_TEMPLATE/`) | me | done |
| D4 | Comparison pages already exist (`docs-site/blog/*vs*`). Re-check their claims against current docs before sharing them | me | done (#66): five posts corrected, each with a dated note |
| D5 | Deeper public-issue sweep: Bifrost, Helicone, Langfuse, OpenRouter and more themes (audit logs behind a paywall, per-team model access, residency). The first attempt hit GitHub's secondary rate limit; run it slowly, with a pause between searches | me | done 2026-11-09, found nothing (see log). Helicone skipped: it is in maintenance mode. Langfuse and OpenRouter not searched |
| D6 | Drafts, not sent: a reply to the #22966 thread, a Show HN, a Reddit post, a LinkedIn post (kept out of the repo, because they name real people) | me | todo |
| D7 | Publish anything: comment on an issue, post anywhere, email anyone | **owner says yes first** | done for the items in the log; Hacker News, Reddit, LinkedIn and X are the owner's to paste |
| D8 | Hosted public demo (the biggest conversion lever; deployment is parked) | **owner** | parked |
| D9 | Turn on GitHub Discussions for the repo | **owner** (repo setting) | done; the post is at [#63](https://github.com/Rayyan-Oumlil/OpenProxyAI/discussions/63) |

## Log (real signals and what was sent)
| Date | What | Link |
|---|---|---|
| 2026-11-09 | Merged the Apache-2.0 LICENSE (the repo was public with none) and the fallback-closure post; set the repo description and topics | #58, #59 |
| 2026-11-09 | Commented on the matching LiteLLM issue (public, from the owner's account, approved) | [comment](https://github.com/BerriAI/litellm/issues/22966#issuecomment-6748772669) |
| 2026-11-09 | Opened a PR adding OpenProxyAI to a large LLMOps list (approved) | [PR](https://github.com/tensorchord/Awesome-LLMOps/pull/1139) |
| 2026-11-09 | Six email drafts were saved in Gmail with no recipients, then deleted at the owner's request; nothing was emailed | |
| 2026-11-09 | Three more list PRs (approved): [MCP gateways](https://github.com/e2b-dev/awesome-mcp-gateways/pull/128), [AI governance](https://github.com/agentrust-io/awesome-ai-governance/pull/211), [LLMOps](https://github.com/InftyAI/Awesome-LLMOps/pull/698). Skipped lists that need 10+ stars (we have 2) or are tiny or stale |  |
| 2026-11-09 | Recipient search for the email drafts found no verified published addresses (only company blogs, funding news and competitors). Nothing sent. The owner dropped email outreach, and the six Gmail drafts were deleted |  |
| 2026-11-09 | Slow sweep (12-15s between searches, nine queries): Bifrost "data residency" and "sensitive data", Portkey gateway "data residency" and "sensitive data", LiteLLM "audit log enterprise" and "sensitive data model", and three repo-independent searches on fallback, residency and data classification. **No matching thread.** Hits were unrelated: a per-key proxy request, a plugin request, an old audit-log rendering bug. Together with the first sweep this means public issue trackers hold one close match (LiteLLM #22966) and nothing else | |
| 2026-11-09 | Corrected five comparison posts against vendors' own pages. Found Helicone in maintenance mode (acquired by Mintlify), Cloudflare now has guardrails, DLP and spend limits, LiteLLM has an Admin UI, and LiteLLM's v1.107.0 was reported compromised on 2026-10-21 (our pin excludes it) | #66 |
| | Held back on purpose: replies to unrelated LiteLLM threads (would read as spam), and a reply on audit-log paywalls (no matching thread found yet) | |

Public forks created for those PRs (GitHub cannot make a fork of a public repo private; delete each one after its PR is merged or closed): 
`Awesome-LLMOps`, `awesome-mcp-gateways`, `awesome-ai-governance`, `Awesome-LLMOps-1` under the owner's account.

Real signals so far: none (no replies yet). Add each reply, star, issue or call here with a date.

## Rules
- Nothing is posted, commented or emailed without the owner's yes in that conversation, each time.
- Email only addresses a person or company published themselves. Never anyone at the owner's employer.
- Real people's names and contact details stay out of the repo. Link to the public thread instead.
- Count only real signals. Log them in this file with a date and a link.
