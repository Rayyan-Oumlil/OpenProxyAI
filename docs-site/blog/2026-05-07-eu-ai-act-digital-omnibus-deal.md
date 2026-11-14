---
slug: eu-ai-act-digital-omnibus-deal
title: "EU AI Act: high-risk rules slip to 2027. Build the logging now"
tags: [security, engineering]
description: "EU negotiators struck a provisional deal on 7 May 2026 that moves high-risk AI Act obligations to December 2027 and August 2028. What changed, what did not, and the engineering work worth starting anyway."
---

On 7 May 2026, the Council presidency and European Parliament negotiators reached a provisional deal to change the EU AI Act. The headline is a delay. Obligations for high-risk AI systems would start in December 2027 for stand-alone systems and August 2028 for AI embedded in products, instead of the original dates. If your team was racing an August 2026 deadline, that is real breathing room. It is also a trap if the breathing room turns into "we will do it later", because the slowest part of the work is the part that cannot be rushed.

{/* truncate */}

![A timeline. Stand-alone high-risk systems move from August 2026 to 2 December 2027. Systems embedded in products move to 2 August 2028. Below, three things to build now: a per-request audit trail, rules on which data may reach which model, and a reviewable path for people.](/img/blog/eu-ai-act-digital-omnibus-deal.svg)

## What was agreed

This is a provisional agreement. It still needs endorsement from both the Council and the Parliament and a legal clean-up before it becomes law, so treat the details as likely, not final. According to a summary published by Lewis Silkin on the day of the deal, it includes:

| Topic | What the deal says |
|---|---|
| Stand-alone high-risk systems | Rules apply from 2 December 2027 |
| High-risk AI embedded in products | Rules apply from 2 August 2028 |
| New ban | AI tools that generate non-consensual sexual content or child sexual abuse material |
| Registration | Providers must register a system in the EU database even when they consider it exempt from high-risk classification |
| Transparency for AI-generated content | The grace period shrinks from six months to three, with a new date of 2 December 2026 |
| Smaller companies | Simplified documentation relief extends to small mid-caps, up to 500 employees |
| Sandboxes | Member states get until 2 August 2027 to set up regulatory sandboxes |

The architecture of the law stands. What moved is the calendar.

## What did not change

The requirements themselves. The AI Act's high-risk chapter still asks for automatic event logging over a system's lifetime (Article 12), a design that lets people oversee the system while it runs (Article 14), and, for organizations that deploy these systems, keeping the logs they control for a period that fits the purpose (Article 26). A later date does not make those requirements smaller. It gives you more time to meet them well.

Whether any of this applies to you depends on what your AI systems do. High-risk covers areas such as hiring, credit decisions and education. A chat assistant that drafts internal emails is a different story. Start by listing your AI use cases and which ones touch the high-risk areas, then plan from that list.

## Why engineers should not wait

Three capabilities take longer to build than a policy document, and all three are useful the day you finish them.

1. **A record of what happened.** For any AI call, who made it, which model served it, what policy decided, what it cost. Retrofitting this into ten applications that each call providers directly is slow. Putting it in one place is not.
2. **Rules that decide which data reaches which model.** A model that is fine for public text may be wrong for customer records. You want that decision made by configuration, in one place, with a visible result.
3. **A path for people to review.** Someone has to look at the records, and someone has to be able to change the rules and see the effect before it goes live.

## How OpenProxyAI helps

OpenProxyAI is an open-source, self-hosted gateway. Your applications send every model call to one OpenAI-compatible endpoint, and the gateway applies the same controls to all of them.

**An audit record for every request.** Each request through the gateway is logged after the response goes out, so logging never slows your application. The record covers who called, with which key, the model and provider, tokens, cost, latency, the status, the policy decision, the routing decision and whether the cache answered. By default it keeps metadata, not what users typed. Entries are write-once: nothing in the request path edits them later. Admins can search and filter the log, and export a report for an internal or external reviewer. See [Audit logging](/security/audit-logging).

**Policy controls you can see and test.** An organization policy sets a model allowlist, blocked keywords, personal data detection and prompt-injection checks. In enforce mode, a request that breaks a rule is refused with status 446 before it reaches any provider, and the refusal explains itself. In log-only mode, the same rules run and record what they would have done, so you can measure before you enforce. See [Policies and guardrails](/core-concepts/policies-and-guardrails) and [Managing policies](/admin-console/managing-policies).

**Data-class routing.** Every request gets a data class, from a built-in detector, the caller's header and your organization's default. A registry of vetted models records, for each one, the highest class it may receive, its regions, a risk rating and its retention terms. In enforce mode, a model serves a request only if the registry allows it for that class. Admins can preview any hypothetical request first and see which model would serve it and why every other model was ruled out, without sending anything. See [Provider routing](/core-concepts/provider-routing).

**Tool access for agents.** If agents call tools through the gateway, each tool call is checked against policy and written to the same audit log. Grants limit which roles, teams, users or keys can call which tools. See [MCP gateway](/guides/mcp-gateway).

## A worked scenario

A recruiting team wants an assistant to summarize candidate notes. Candidate notes are the kind of use the high-risk list worries about, so the team does three things in one afternoon. It tags the traffic with a label for the recruiting app. It sets a data class for that traffic and routes it only to the models in the registry that are cleared for it, in the regions it approved. And it turns on log-only mode for the personal data checks for a week, reads the results, then switches to enforce. When a reviewer asks "what did the assistant do in March", the answer is a filtered view of the log, not an archaeology project.

None of this decides whether the use case is high-risk, and none of it replaces the documentation the law asks providers to keep. It gives the engineering side of the answer a solid base.

## What to do now

- [ ] List every AI use case and mark which ones touch high-risk areas.
- [ ] Route all model calls through one gateway so there is one audit trail.
- [ ] Decide your retention need. The gateway's log windows are set by plan: 7 days on Community, 30 on Team, 90 on Business and 365 on Enterprise. Export on a schedule if you need longer.
- [ ] Define data classes and approve models per class in a registry.
- [ ] Run policy in log-only mode first, review, then enforce.
- [ ] Name who reviews the records and how often.
- [ ] Watch for formal adoption of the deal and re-check the dates then.

## Good to know

OpenProxyAI ships policy templates and controls. It is not a certification, and using it does not by itself make a system compliant with the AI Act. The gateway records and controls what passes through it, so calls that bypass it are not covered. That is a good reason to make it the only route to your providers.

## Try it

```bash
git clone https://github.com/Rayyan-Oumlil/OpenProxyAI
cd OpenProxyAI
docker compose -f docker-compose.demo.yml up --build
```

This needs Docker and no provider key. The console opens at http://localhost:5173 with sample traffic in the log. If it is useful, star the repo or open an issue with what you would like to see next.

## Sources

- [The Council and Parliament agree to slim down and delay parts of the EU AI Act](https://www.lewissilkin.com/insights/2026/05/07/the-council-and-parliament-agree-to-slim-down-and-delay-parts-of-the-eu-ai-act-102ms0v), Lewis Silkin, 7 May 2026. Dates, the new ban, registration, transparency grace period and next steps.
- [AI Act, Article 12: record-keeping](https://artificialintelligenceact.eu/article/12/), [Article 14: human oversight](https://artificialintelligenceact.eu/article/14/) and [Article 26: obligations of deployers](https://artificialintelligenceact.eu/article/26/). Text of the requirements.
- Internal: [Audit logging](/security/audit-logging), [Compliance templates](/guides/compliance-templates), [Request pipeline](/core-concepts/request-pipeline).

These statements are based on the sources above and on OpenProxyAI's behavior at the date of this post. The agreement was provisional on that date.
