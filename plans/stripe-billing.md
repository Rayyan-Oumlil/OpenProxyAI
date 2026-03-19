# Plan — Stripe Billing Integration

**Objective:** Accept payment for Starter ($2,500/mo), Growth ($7,500/mo), Enterprise plans.
**Scope:** Stripe Checkout, Customer Portal, webhook sync, admin console billing UI.
**Created:** 2026-03-19
**Reviewed:** Opus adversarial review — 5 CRITICAL, 7 HIGH fixed in this version.
**Status:** Ready to execute

---

## Context Brief (read this cold)

- Stack: FastAPI backend, React + Vite + shadcn/ui admin console
- `organizations` table has `plan` column (free/starter/growth/enterprise), no Stripe fields yet
- `PLAN_FEATURES` dict in `backend/app/config.py` gates features per plan
- `plan_service.py` enforces plan limits at request time
- No billing routes exist — add to `backend/app/routes/billing.py`
- Frontend features in `admin-console/src/features/` — add `billing/` here
- Auth: checkout + portal endpoints require `current_user.role == "admin"` (not just any JWT)
- Webhook endpoint: PUBLIC but Stripe-signature verified + idempotency guard
- **Stripe is the source of truth for plan state** — remove manual plan dropdown from OrganizationSettingsPage

---

## Dependency Graph

```
Step 1 (DB migration: 3 new columns + stripe_events table)
  └── Step 2 (billing_service.py)
        ├── Step 3 (backend routes)   ─┐ parallel
        └── Step 4 (frontend UI)      ─┘
              └── Step 5 (tests)
Step 6 (env config + docs + lock down plan override)  ← run with Step 1
```

---

## Step 1 — DB migration

**Branch:** `feat/stripe-migration`
**Risk:** low — additive only

### Tasks
- [ ] Add 3 columns to `backend/app/models/organization.py`:
  ```python
  stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
  stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
  stripe_subscription_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
  # values: active, past_due, canceled, paused, incomplete — mirrors Stripe statuses
  ```
- [ ] Create `stripe_events` table for idempotency (prevents duplicate webhook processing):
  ```python
  class StripeEvent(UUIDPrimaryKeyMixin, Base):
      __tablename__ = "stripe_events"
      event_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
      processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
  ```
- [ ] Generate migration: `alembic revision --autogenerate -m "add_stripe_billing_fields"`
- [ ] Review migration — confirm no drops, only ADD COLUMN + CREATE TABLE
- [ ] Apply locally: `alembic upgrade head`
- [ ] Add `stripe_customer_id`, `stripe_subscription_id`, `stripe_subscription_status` to `OrganizationResponse` schema

### Verification
```bash
cd backend && alembic upgrade head
python -m pytest backend/tests/test_organizations.py -q
```

### Exit criteria
- Migration applies cleanly
- Existing org tests still pass
- 3 new fields in `OrganizationResponse`

---

## Step 2 — billing_service.py

**Branch:** `feat/stripe-service` (branch off Step 1)
**Risk:** low — new file

### Tasks
- [ ] Add `stripe>=7.0.0` to `backend/requirements.txt`
- [ ] Add to `backend/app/config.py` `Settings` class with validators:
  ```python
  STRIPE_SECRET_KEY: str = ""
  STRIPE_WEBHOOK_SECRET: str = ""       # must start with whsec_
  STRIPE_STARTER_PRICE_ID: str = ""
  STRIPE_GROWTH_PRICE_ID: str = ""
  STRIPE_SUCCESS_URL: str = "http://localhost:5173/billing?success=1"
  STRIPE_CANCEL_URL: str = "http://localhost:5173/billing?canceled=1"

  @field_validator("STRIPE_SECRET_KEY")
  def stripe_key_must_not_be_empty_in_prod(cls, v, info):
      # warn but don't hard-fail — Stripe is optional during early dev
      return v
  ```
- [ ] Add to `PLAN_FEATURES` comment: Enterprise has no Stripe price ID — handled manually
- [ ] Create `backend/app/services/billing_service.py`:

  **`get_or_create_customer(org, db)`**
  - Use `SELECT ... FOR UPDATE` on the org row to prevent TOCTOU race
  - If `org.stripe_customer_id` is set, return it
  - Call `stripe.Customer.create(email=org.owner_email, metadata={"org_id": str(org.id)})`
  - Save to DB in same transaction

  **`create_checkout_session(org, plan, db)`**
  - Call `get_or_create_customer` first
  - Map plan → price ID: `PRICE_MAP = {settings.STRIPE_STARTER_PRICE_ID: "starter", settings.STRIPE_GROWTH_PRICE_ID: "growth"}`
  - Reverse map for checkout: `PLAN_TO_PRICE = {"starter": settings.STRIPE_STARTER_PRICE_ID, "growth": settings.STRIPE_GROWTH_PRICE_ID}`
  - If `plan == "enterprise"`: raise `ValueError("Enterprise requires manual setup")`
  - Create Stripe Checkout session with `mode="subscription"`
  - Return `session.url`

  **`create_portal_session(org, db)`**
  - Require `org.stripe_customer_id` — raise 400 if missing (never subscribed)
  - Create Stripe Customer Portal session
  - Return `session.url`

  **`handle_webhook(payload: bytes, sig_header: str, db)`**
  - Step 1: Verify signature — `stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)`
  - On `SignatureVerificationError`: raise HTTP 400 immediately
  - Step 2: Idempotency check — `SELECT FROM stripe_events WHERE event_id = event.id`
  - If found: return immediately (already processed)
  - Step 3: Dispatch on `event.type` in a single DB transaction:
    - `checkout.session.completed`:
      - Only proceed if `session.payment_status == "paid"` (guards against SEPA/3DS delays)
      - Save `stripe_customer_id` and `stripe_subscription_id` to org
      - Set `stripe_subscription_status = "active"`
    - `invoice.paid`:
      - Look up org by `stripe_customer_id`
      - Map price ID → plan name (if unrecognized price ID: log warning, do NOT change plan)
      - Update `org.plan` and set `stripe_subscription_status = "active"`
    - `invoice.payment_failed`:
      - Set `stripe_subscription_status = "past_due"` on org
      - Log admin audit event `billing.payment_failed`
    - `customer.subscription.updated`:
      - Update `stripe_subscription_status` to `event.data.object.status`
      - If status is `active`: resolve price ID → plan, update `org.plan`
      - If price ID unrecognized: log warning, skip plan change
    - `customer.subscription.deleted`:
      - Set `org.plan = "free"`, `stripe_subscription_status = "canceled"`, `stripe_subscription_id = None`
      - Log admin audit event `billing.subscription_canceled`
  - Step 4: Insert `StripeEvent(event_id=event.id)` into DB (same transaction as plan mutation)
  - Log admin audit event for all plan changes: actor = `"stripe-webhook"`, action = `"billing.plan_changed"`

### Verification
```bash
python -c "from app.services.billing_service import handle_webhook; print('ok')"
```

### Exit criteria
- Module imports cleanly
- All functions present with correct signatures
- TOCTOU guard (`SELECT FOR UPDATE`) in `get_or_create_customer`
- Idempotency table insert + plan mutation in same transaction

---

## Step 3 — Backend billing routes

**Branch:** `feat/stripe-routes` (branch off Step 2)
**Parallel with:** Step 4

### Tasks
- [ ] Create `backend/app/routes/billing.py`:

  ```
  POST /api/v1/billing/checkout
    Auth: current_user.role == "admin"  ← NOT just any JWT
    Body: {"plan": "starter" | "growth"}
    Returns: {"checkout_url": "..."}
    Errors: 400 if plan == "enterprise", 400 if Stripe not configured

  POST /api/v1/billing/portal
    Auth: current_user.role == "admin"
    Body: none
    Returns: {"portal_url": "..."}
    Errors: 400 if org has no stripe_customer_id

  POST /api/v1/billing/webhook
    Auth: NONE (public)
    Headers: Stripe-Signature (required)
    Body: raw bytes — use `body = await request.body()` as FIRST operation
          DO NOT declare a Pydantic body model — this consumes the stream
    Returns: {"received": true}
    Errors: 400 on signature mismatch
  ```

- [ ] **Webhook raw body pattern** (critical — do it exactly this way):
  ```python
  @router.post("/webhook")
  async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
      payload = await request.body()          # ← FIRST, before anything else
      sig = request.headers.get("stripe-signature", "")
      await billing_service.handle_webhook(payload, sig, db)
      return {"received": True}
  ```
- [ ] Register in `backend/app/main.py`: `app.include_router(billing_router, prefix="/api/v1/billing", tags=["billing"])`
- [ ] Lock down plan override: in `backend/app/routes/organizations.py`, if `stripe_subscription_id` is set on the org, reject any `PATCH` request that includes a `plan` field with HTTP 409: `"Plan is managed by Stripe. Use billing portal to change plans."`

### Verification
```bash
python -m pytest backend/tests/test_billing.py -q
# confirm routes in OpenAPI docs
uvicorn app.main:app --reload  # check /docs
```

### Exit criteria
- All 3 routes in `/docs`
- Checkout + Portal return 401 without auth, 403 for non-admin
- Webhook returns 400 on bad signature
- Plan override returns 409 when Stripe-managed

---

## Step 4 — Frontend billing UI

**Branch:** `feat/stripe-frontend` (branch off Step 1, parallel with Step 3)

### Tasks
- [ ] Create `admin-console/src/features/billing/BillingPage.tsx`:
  - Show current plan, limits, `stripe_subscription_status` (badge: active / past_due / canceled)
  - Upgrade buttons (Starter / Growth) — call `POST /api/v1/billing/checkout`, redirect to URL
  - "Manage billing" button — call `POST /api/v1/billing/portal`, redirect to URL (disabled if no `stripe_customer_id`)
  - **`?success=1` handling:** show "Payment processing..." state → poll `GET /api/v1/organizations/current` every 3s for up to 30s until `plan` changes → then show success toast. If 30s elapses without change: show "Your plan will update shortly."
  - **`?canceled=1` handling:** show "Checkout was canceled. No charges were made."
- [ ] Add route in `admin-console/src/App.tsx`: `<Route path="billing" element={<BillingPage />} />`
- [ ] Add "Billing" nav item to `admin-console/src/features/layout/AdminLayout.tsx`
- [ ] **Remove plan `<select>` from `OrganizationSettingsPage.tsx`** — replace with read-only plan display + link to `/billing`
- [ ] Update `admin-console/src/api/types.ts`:
  ```typescript
  stripe_customer_id?: string | null
  stripe_subscription_id?: string | null
  stripe_subscription_status?: string | null
  ```

### Verification
```bash
cd admin-console && npm run build  # must exit 0, no type errors
```

### Exit criteria
- `npm run build` passes
- BillingPage accessible at `/billing` route
- Plan dropdown removed from OrganizationSettingsPage
- Polling logic present for post-checkout success state

---

## Step 5 — Tests

**Branch:** `feat/stripe-tests` (branch off Steps 3+4 merged)

### Tasks
- [ ] Create `backend/tests/test_billing.py` with these cases:
  - `test_checkout_returns_url` — mock Stripe SDK, assert 200 + checkout_url
  - `test_checkout_requires_admin` — developer role → 403
  - `test_checkout_requires_auth` — no token → 401
  - `test_portal_returns_url`
  - `test_portal_returns_400_if_no_customer` — org with no stripe_customer_id
  - `test_webhook_invalid_signature_returns_400`
  - `test_webhook_idempotency` — same event_id twice, second call is no-op
  - `test_webhook_invoice_paid_syncs_plan`
  - `test_webhook_invoice_payment_failed_sets_past_due`
  - `test_webhook_subscription_deleted_downgrades_to_free`
  - `test_webhook_unknown_price_id_does_not_change_plan`
  - `test_webhook_checkout_session_unpaid_does_not_upgrade_plan` — payment_status != "paid"
  - `test_plan_override_rejected_when_stripe_managed` — PATCH org with plan field → 409
- [ ] Run full suite: `python -m pytest backend/tests/ -q` — must stay ≥ 294 passing

### Exit criteria
- All 13+ billing tests green
- Zero regressions in existing suite

---

## Step 6 — Env config, docs, plan override lockdown

**Branch:** `feat/stripe-env` (independent, run with Step 1)

### Tasks
- [ ] Add to `backend/.env.example`:
  ```
  STRIPE_SECRET_KEY=sk_test_...
  STRIPE_WEBHOOK_SECRET=whsec_...
  STRIPE_STARTER_PRICE_ID=price_...
  STRIPE_GROWTH_PRICE_ID=price_...
  # STRIPE_SUCCESS_URL and STRIPE_CANCEL_URL default to localhost:5173
  ```
- [ ] Add startup validation in `backend/app/main.py` lifespan:
  ```python
  if settings.STRIPE_SECRET_KEY and not settings.STRIPE_WEBHOOK_SECRET:
      logger.error("STRIPE_WEBHOOK_SECRET is required when STRIPE_SECRET_KEY is set")
  ```
- [ ] Create `docs/guides/stripe-setup.md`:
  - How to get price IDs from Stripe dashboard (create recurring products)
  - How to set up webhook endpoint pointing to `POST /api/v1/billing/webhook`
  - How to use Stripe CLI locally: `stripe listen --forward-to localhost:8000/api/v1/billing/webhook`
  - Note: use `sk_test_` + `pk_test_` for dev, `sk_live_` for prod — never mix
- [ ] Update `docs/roadmap.md` — mark Phase 6.1 in-progress
- [ ] Add `plans/` to `.gitignore` or commit — decide and document

---

## Execution Order

```
Day 1 AM:  Step 1 + Step 6 in parallel
Day 1 PM:  Step 2
Day 2 AM:  Step 3 + Step 4 in parallel (separate sessions)
Day 2 PM:  Step 5
Day 2 EOD: PR per step, merge: 1 → 6 → 2 → 3 → 4 → 5
```

## Rollback

All steps additive. To rollback:
```bash
alembic downgrade -1   # removes stripe columns + stripe_events table
# delete billing.py, billing_service.py, billing/ feature folder
# revert organizations.py PATCH guard
# restore plan dropdown in OrganizationSettingsPage
```

## Before You Start — Get These From Stripe

1. Create account at stripe.com (test mode)
2. Create two recurring products:
   - "OpenProxyAI Starter" — $2,500/mo → copy Price ID
   - "OpenProxyAI Growth" — $7,500/mo → copy Price ID
3. In Stripe dashboard → Webhooks → Add endpoint:
   - URL: `https://your-domain.com/api/v1/billing/webhook`
   - Events to listen for: `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted`
   - Copy webhook signing secret (`whsec_...`)
4. Copy secret API key (`sk_test_...`)
5. Add all 4 values to `.env`
