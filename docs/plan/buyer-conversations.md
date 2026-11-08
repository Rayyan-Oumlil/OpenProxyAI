# Buyer conversations kit (the gate before Phase 2)

Goal: five 20-minute conversations with the people who say yes or no to an AI gateway. Their answers decide
Phase 2 scope together with D2 and D5 (`execution-plan.md`). Question list: `research-brief.md`. Stop building
new features until five are logged.

## Who to talk to
- Heads of security, platform engineering or IT at **health-tech, fintech or credit unions, 100-1,000 people**,
  who already tried LiteLLM, ChatGPT Enterprise or a similar tool and hit a security review.
- Not: anyone at your employer, or anyone you reach through that role. Check your employment agreement
  (outside work, IP, conflict of interest) before you pitch any financial institution.
- Where: LinkedIn (security/platform titles), r/selfhosted and LiteLLM/Portkey community threads, your UdeM and
  hackathon network, warm intros. Aim for 15 outreach messages to get 5 calls.

## Outreach (short, no pitch)
**EN**
> Hi {name}, I'm building an open-source gateway that sits between a company's teams and LLM providers
> (one key, audit trail, policy, budgets, MCP tool control). I'm not selling anything yet: I'd like 20 minutes
> to hear how {company} handles LLM access and what security asked for. Would a call this week work?

**FR**
> Bonjour {nom}, je construis une passerelle open source entre les équipes d'une entreprise et les fournisseurs
> de LLM (une clé, journal d'audit, politiques, budgets, contrôle des outils MCP). Je ne vends rien pour
> l'instant : j'aimerais 20 minutes pour comprendre comment {entreprise} encadre l'accès aux LLM et ce que la
> sécurité a exigé. Seriez-vous disponible cette semaine ?

## The 20 minutes
| Min | Do | Notes |
|---|---|---|
| 0-2 | Thank, say what you are and are not (no sales pitch, learning call) | Ask permission to take notes |
| 2-8 | Q1 How do teams call LLMs today, who approved it? Q2 What did security ask for, where did you get stuck? | Listen. Do not mention features yet |
| 8-11 | Q3 Last time sensitive data went into a prompt, how would you have known? | The pain that PII blocking and audit answer |
| 11-16 | Q4 Show the demo (video, or live: `docker compose -f docker-compose.demo.yml up`) | Allowed 200, PII 403, audit trace, daily-budget stop, MCP tool drift |
| 16-19 | Q5 What would stop you running this next month? | The blockers are the roadmap |
| 19-20 | Q6 Would you pay, how much, who signs? Ask for a 30-day design-partner pilot | Silence after the ask is fine |

Video: https://github.com/Rayyan-Oumlil/OpenProxyAI/releases/tag/walkthrough-v1

## Do not say (unverified, see research-brief.md)
Competitor prices, the AI Act date claim, "immutable audit", any HIPAA/SOC 2 certification (we have a mapping, not
a certification), productivity multipliers.

## Log (copy one row per call)
| # | Date | Name / role / company size | Today's LLM setup | Security blockers | Data-leak story | Demo reaction | Would stop adoption | Pays? How much? Who signs? | Pilot yes/no |
|---|---|---|---|---|---|---|---|---|---|

## After five calls
1. Count: which pain came up in 3+ calls (audit evidence, PII, MCP/agent control, routing by data class)?
2. That pain is the answer to D2 (lead wedge). Compare with the default in `execution-plan.md`.
3. Any pilot yes: that is the first design partner. Their blockers become Phase 2.
4. If fewer than 3 calls name any of the four pains, stop and re-think the segment before building.
