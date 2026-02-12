# Business Model & Pricing Strategy

## 🎯 Business Model: Open Core

### The Model

```
┌────────────────────────────────────────┐
│          Open Source (Free)            │
│  • Basic LLM proxy                     │
│  • Cost tracking                       │
│  • API keys                            │
│  • Community support                   │
│  • Self-hosted                         │
└──────────────┬─────────────────────────┘
               │
               │ Value Ladder
               ▼
┌────────────────────────────────────────┐
│       Enterprise (Paid)                │
│  • SSO / SAML                          │
│  • Multi-tenancy                       │
│  • Advanced audit logs                 │
│  • Policy enforcement (DLP)            │
│  • Compliance dashboard                │
│  • SLA & support                       │
│  • On-premise deployment               │
└────────────────────────────────────────┘
```

### Why Open Core?

**Bottom-Up Adoption:**
1. Engineer discovers on GitHub/HN
2. Downloads OSS, tries locally (< 5 min)
3. Loves it, rolls out to team
4. Team hits limits (SSO needed, 50+ users)
5. Security team requires audit/compliance
6. Company pays for Enterprise

**Math:**
- 1,000 OSS users → 10 convert to paid (1%) = $250K ARR
- 10,000 OSS users → 100 convert (1%) = $2.5M ARR

---

##💰 Pricing Model

### Tier Structure

| Tier | Price | Target | Key Features |
|------|-------|--------|--------------|
| **Open Source** | Free | Individuals, Startups | Basic proxy, cost tracking, self-hosted |
| **Starter** | $2,500/mo | Small Teams | + SSO, 50 users, email support |
| **Growth** | $7,500/mo | Mid-size Companies | + 200 users, policy engine, phone support |
| **Enterprise** | Custom | Large Orgs | + Unlimited users, on-premise, SLA, dedicated CSM |

### Detailed Pricing

#### **Open Source (Community Edition)**

**Price:** $0

**Includes:**
- ✅ LLM proxy (OpenAI, Anthropic, Azure)
- ✅ Basic cost tracking
- ✅ API key authentication
- ✅ Simple audit logs (30 days)
- ✅ Admin dashboard (read-only)
- ✅ Docker deployment
- ✅ Community support (Discord, GitHub)

**Limits:**
- ⚠️ 10 users max
- ⚠️ 10,000 requests/month
- ⚠️ No SSO
- ⚠️ No policy enforcement
- ⚠️ No SLA

**Ideal for:** Solo developers, small startups, POCs

---

#### **Starter**

**Price:** $2,500/month ($30K/year)

**Everything in Open Source, plus:**
- ✅ SSO (Google, Microsoft, Okta)
- ✅ Up to 50 users
- ✅ 100,000 requests/month included
- ✅ Advanced audit logs (90 days retention)
- ✅ Department-level analytics
- ✅ Budget controls (per user, per dept)
- ✅ Email support (24h response)
- ✅ Assisted setup (1 hour)

**Add-ons:**
- +$25/user/month for 51-100 users
- +$0.01/request above 100K

**Ideal for:** Teams of 10-50, need basic governance

**Target Customer:**
- Series A/B startups
- Small fintech companies
- Digital agencies with enterprise clients

---

#### **Growth**

**Price:** $7,500/month ($90K/year)

**Everything in Starter, plus:**
- ✅ Up to 200 users
- ✅ 500,000 requests/month included
- ✅ Policy enforcement engine
  - PII detection/redaction
  - Custom content policies
  - Model restrictions
- ✅ Advanced RBAC
- ✅ Audit log export (compliance)
- ✅ 1-year audit retention
- ✅ Priority support (4h response, phone/Slack)
- ✅ Quarterly security reviews

**Add-ons:**
- +$25/user/month for 201+ users
- +$0.008/request above 500K
- On-premise deployment: +$15K/year

**Ideal for:** Growing companies, regulatory requirements

**Target Customer:**
- Series B/C startups
- Healthcare tech companies
- Financial services (< 500 employees)
- Government contractors (cloud)

---

#### **Enterprise**

**Price:** Starting at $25,000/month ($300K/year)

**Everything in Growth, plus:**
- ✅ Unlimited users
- ✅ Custom request limits
- ✅ On-premise deployment (included)
- ✅ Air-gapped support
- ✅ Advanced compliance
  - SOC 2 reports
  - HIPAA compliance assistance
  - GDPR tools
  - Custom compliance mapping
- ✅ 99.9% SLA
- ✅ Dedicated customer success manager
- ✅ 24/7 priority support (1h response)
- ✅ Custom integrations
- ✅ Training & onboarding
- ✅ Annual security audit included

**Custom Features:**
- Custom AI models/providers
- Custom policy logic
- Multi-region deployment
- Dedicated infrastructure
- White-labeling

**Ideal for:** Large enterprises, highly regulated

**Target Customer:**
- Fortune 1000 companies
- Banks, insurance (500+ employees)
- Healthcare systems
- Government agencies

---

## 📊 Revenue Projections

### Year 1 (Bootstrapped)

**Target: $500K ARR**

| Month | OSS Users | Paid Customers | MRR | ARR |
|-------|-----------|----------------|-----|-----|
| 1-4 | 100 | 0 | $0 | $0 |
| 5 | 300 | 1 (Starter) | $2,500 | $30K |
| 6 | 500 | 2 (1+1) | $5,000 | $60K |
| 7-8 | 1,000 | 4 | $10,000 | $120K |
| 9-10 | 2,500 | 8 | $22,500 | $270K |
| 11-12 | 5,000 | 12 | $42,000 | $504K |

**Customer Mix (Year 1):**
- 10× Starter ($2.5K/mo) = $25K MRR
- 2× Growth ($7.5K/mo) = $15K MRR
- **Total: $40K MRR = $480K ARR**

### Year 2 (With Funding or Profitable)

**Target: $5M ARR**

| Quarter | Paid Customers | Avg ACV | ARR |
|---------|----------------|---------|-----|
| Q1 | 20 | $50K | $1M |
| Q2 | 35 | $60K | $2.1M |
| Q3 | 50 | $65K | $3.25M |
| Q4 | 70 | $70K | $4.9M |

**Customer Mix (Year 2):**
- 40× Starter ($30K/year) = $1.2M
- 25× Growth ($90K/year) = $2.25M
- 5× Enterprise ($300K/year) = $1.5M
- **Total: $4.95M ARR**

### Year 3 (Scale)

**Target: $20M ARR**

**Customer Mix:**
- 200× Starter = $6M
- 100× Growth = $9M
- 20× Enterprise = $6M
- **Total: $21M ARR**

---

## 💵 Unit Economics

### Customer Acquisition Cost (CAC)

**Year 1 (Organic):**
- Marketing: $0 (content, OSS)
- Sales: $0 (founder)
- **CAC: $0-500/customer**

**Year 2 (Light Sales):**
- Marketing: $5K/month
- Sales hire: $100K/year
- 50 customers = $160K / 50
- **CAC: $3,200/customer**

**Target (Mature):**
- **CAC: $10K-15K/customer**
- **Payback: 6-9 months**

### Lifetime Value (LTV)

**Starter Customer:**
- ACV: $30K
- Gross margin: 85% ($25.5K)
- Avg lifetime: 3 years
- **LTV: $76.5K**

**Growth Customer:**
- ACV: $90K
- Gross margin: 88% ($79.2K)
- Avg lifetime: 4 years
- **LTV: $316.8K**

**Enterprise Customer:**
- ACV: $300K+
- Gross margin: 90% ($270K)
- Avg lifetime: 5 years
- **LTV: $1.35M+**

### LTV:CAC Ratios

| Segment | LTV | CAC | LTV:CAC | Target |
|---------|-----|-----|---------|--------|
| Starter | $76.5K | $3K | 25:1 | >3:1 ✅ |
| Growth | $316.8K | $10K | 32:1 | >3:1 ✅ |
| Enterprise | $1.35M | $50K | 27:1 | >3:1 ✅ |

**Excellent unit economics due to open-source funnel**

---

## 📈 Growth Levers

### 1. Open Source Funnel (Primary)

**Mechanics:**
```
GitHub Star → Try locally → Love it → Tell team → 
Team adopts → Hit limits → Talk to sales → Buy Enterprise
```

**Conversion Metrics:**
- GitHub star → Trial: 10%
- Trial → Active user: 30%
- Active user (OSS) → Paid: 1-2%

**Example:**
- 10,000 stars → 1,000 trials → 300 active → 3-6 paid

### 2. Content Marketing

**Strategy:**
- Blog: Technical deep dives (LLM security, cost optimization)
- SEO: Rank for "LLM proxy", "OpenAI cost tracking"
- YouTube: Setup tutorials, architecture videos
- Twitter: Daily tips, feature updates

**Target: 10K organic visits/month by month 12**

### 3. Community-Led Growth

**Mechanics:**
- Discord server for users
- Contributors as champions
- Case studies from OSS users
- Integration marketplace (community-built)

**Goal: 500+ Discord members by month 6**

### 4. Product-Led Sales

**Trigger-based outreach:**
- OSS user hits 50 users → Email about Starter
- Starter customer at 48/50 seats → Upsell Growth
- Growth customer using policy logs → Upsell Enterprise

**Automated nurture sequences**

### 5. Channel Partnerships (Year 2+)

**Potential partners:**
- Cloud providers (Azure, AWS marketplaces)
- Systems integrators (Deloitte, Accenture)
- Security vendors (co-marketing)

---

## 🎯 Pricing Psychology

### Why This Pricing Works

#### **$2,500/mo Starter = "Department Budget"**
- Not a "company decision" ($30K/year)
- Engineering lead can approve
- Credit card purchase ok
- 30-day sales cycle

#### **$7,500/mo Growth = "Initiative Budget"**
- VP-level decision ($90K/year)
- PO required, but not exec committee
- 60-day sales cycle

#### **$25K/mo Enterprise = "Strategic Budget"**
- C-level decision ($300K+/year)
- Procurement process
- 90-180 day sales cycle
- But: high ACV justifies effort

### Anchoring Strategy

**First impression: "Free"**
- OSS version sets anchor at $0
- Any paid version feels reasonable
- No sticker shock

**Then: Value-based**
- "How much does your OpenAI bill cost?"
- "We're 10% of that for governance"
- Easy ROI story

---

## 💳 Payment & Billing

### Payment Methods

**Starter & Growth:**
- Credit card (Stripe)
- ACH transfer
- Wire transfer (>$50K)

**Enterprise:**
- Invoice (Net 30/60)
- Wire transfer
- PO process

### Billing Cycle

**Monthly:**
- Starter, Growth (default)
- Higher churn, but lower friction

**Annual:**
- 2 months free (20% discount)
- Improve cash flow
- Reduce churn

**Enterprise:**
- Annual only
- Quarterly or annual payments

### Usage-Based Overages

**Requests:**
- Starter: $0.01/request above 100K
- Growth: $0.008/request above 500K
- Enterprise: Negotiated rate or unlimited

**Users:**
- $25/user/month above tier limits
- Invoiced monthly

---

## 🔄 Expansion Revenue

### Net Revenue Retention Target: 120%+

**Expansion Paths:**

#### 1. **Add Users**
- Team grows from 30 → 60
- +10 users × $25 = +$250/mo

#### 2. **Upgrade Tier**
- Starter → Growth: +$5K/mo
- Growth → Enterprise: +$17.5K/mo

#### 3. **Add-ons**
- On-premise deployment: +$15K/year
- Dedicated support: +$2K/mo
- Custom integrations: +$10K setup + $1K/mo

#### 4. **Usage Growth**
- Company scales AI usage
- More requests → higher overages
- Natural revenue growth

---

## 🎁 Free Tier Strategy

### Why Free Tier?

**Pros:**
- ✅ Low-friction adoption
- ✅ Viral growth
- ✅ Community advocates
- ✅ Bottom-up into enterprises

**Cons:**
- ❌ Support burden
- ❌ Infrastructure costs
- ❌ Delayed revenue

**Decision: Free tier = OSS (self-hosted only)**
- No free cloud tier
- We don't pay infrastructure
- User pays their own hosting
- Support via community

---

## 📊 Pricing Experiments (Post-Launch)

### Month 6 Test

**Question:** Is $2,500 right for Starter?

**Test:**
- Cohort A: $2,500/mo
- Cohort B: $3,500/mo
- Measure: Conversion rate

**Decision:** Pick price with best $ conversion

### Month 12 Test

**Question:** Should we have a middle tier?

**Current:** Starter ($2.5K) → Growth ($7.5K) = 3x jump

**Test:** Starter ($2.5K) → Pro ($4.5K) → Growth ($7.5K)

**Measure:** 
- Does Pro cannibalize Growth?
- Does Pro increase total revenue?

---

## 🏆 Competitive Pricing Analysis

| Competitor | Model | Price | Our Advantage |
|------------|-------|-------|---------------|
| **LiteLLM** | OSS only | Free | We have paid enterprise features |
| **Azure AI** | Cloud only | Per-usage | We're provider-agnostic |
| **Portkey** | SaaS only | $49+/mo | We have self-hosted option |
| **Helicone** | SaaS only | $50+/mo | We focus on security/compliance |

**Our Position:**
- **Starter cheaper than** SaaS competitors (all-in $2.5K vs. usage-based)
- **Enterprise similar to** large competitors ($300K+)
- **But: Unique value** = security + compliance + on-premise

---

## 📋 Pricing Page Mockup

```markdown
# Pricing

**Start with open source. Upgrade when you need governance.**

┌─────────────────────────────────────────────────────────┐
│                    Open Source                          │
│                        FREE                             │
│                                                         │
│  ✓ LLM proxy (OpenAI, Anthropic, Azure)               │
│  ✓ Cost tracking                                        │
│  ✓ 10 users, 10K requests/month                        │
│  ✓ Self-hosted                                          │
│  ✓ Community support                                    │
│                                                         │
│  [Get Started — GitHub →]                              │
└─────────────────────────────────────────────────────────┘

┌──────────────┬───────────────┬────────────────────────┐
│   Starter    │    Growth     │      Enterprise        │
├──────────────┼───────────────┼────────────────────────┤
│ $2,500/mo    │  $7,500/mo    │      Custom            │
│              │               │                        │
│ Everything   │ Everything    │ Everything in Growth   │
│ in OSS, plus:│ in Starter +: │ plus:                  │
│              │               │                        │
│ • SSO        │ • 200 users   │ • Unlimited users      │
│ • 50 users   │ • Policy      │ • On-premise           │
│ • Advanced   │   engine      │ • 99.9% SLA            │
│   audit logs │ • DLP/PII     │ • Dedicated CSM        │
│ • Email      │   detection   │ • 24/7 support         │
│   support    │ • Phone       │ • SOC 2 assistance     │
│              │   support     │                        │
│ [Start Trial]│ [Start Trial] │ [Contact Sales]        │
└──────────────┴───────────────┴────────────────────────┘

**All plans include:**
✓ Unlimited LLM providers
✓ Real-time cost tracking
✓ Audit logging
✓ API-first architecture
✓ Docker + Kubernetes support
```

---

## 🎯 Sales Playbook

### Starter Tier (Self-Service)

**Target:** Engineering managers, Staff engineers

**Sale motion:**
1. Try OSS for free
2. Hit 10-user limit
3. See "Upgrade" banner
4. 14-day Starter trial (credit card)
5. Auto-convert or cancel

**Tools needed:**
- [ ] Self-serve signup
- [ ] Stripe integration
- [ ] Auto-provisioning
- [ ] In-app upgrade prompts
- [ ] Email onboarding sequence

**Goal: Zero human touch**

---

### Growth Tier (Low-Touch Sales)

**Target:** VPs Engineering, Security leads

**Sale motion:**
1. Starter customer outgrows (50 users)
2. Automated email: "Ready for Growth?"
3. 30-min call with founder (month 1-12)
4. Demo compliance features
5. Send proposal (DocuSign)
6. Close in 1-2 weeks

**Tools needed:**
- [ ] Calendly link
- [ ] Demo environment
- [ ] Proposal template
- [ ] Slack/Discord for support

**Goal: Founder handles until 20+ Growth customers**

---

### Enterprise Tier (High-Touch Sales)

**Target:** CISOs, CTOs, VPs Security

**Sale motion:**
1. Inbound demo request
2. Discovery call (understand requirements)
3. Technical deep-dive (architecture, security)
4. Security review (answer questionnaire)
5. POC/Pilot (30-90 days)
6. Procurement (legal, infosec, finance)
7. Close ( 90-180 days)

**Tools needed:**
- [ ] Sales hire (month 12+)
- [ ] Demo environment (enterprise features)
- [ ] Security questionnaire responses
- [ ] SOC 2 report
- [ ] Reference customers
- [ ] Custom proposals

**Goal: Hire sales rep by $500K ARR**

---

## 💡 Key Takeaways

1. **Open core = best model** for infrastructure software
2. **$2.5K entry point** = department budget (fast close)
3. **3-tier structure** = cover SMB → Enterprise
4. **Usage-based overages** = capture expansion
5. **Self-serve Starter** = scale without sales team
6. **120%+ NRR target** = expansion > new sales
7. **Free = OSS self-hosted** = no infrastructure burden

---

*Next: [Go-to-Market Strategy →](../14_Go_To_Market/gtm_strategy.md)*
