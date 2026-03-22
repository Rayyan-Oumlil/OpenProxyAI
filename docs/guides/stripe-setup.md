# Stripe Setup Guide

> **Quick webhook setup:** [stripe-webhook-setup.md](./stripe-webhook-setup.md) — copy-paste checklist for production.

## 1. Create a Stripe account

Go to [stripe.com](https://stripe.com) and create an account. Use **test mode** during development (the toggle at the top of the dashboard).

## 2. Create products and prices

In the Stripe dashboard → **Products** → **Add product**:

| Product name | Price | Billing |
|---|---|---|
| OpenProxyAI Starter | $2,500.00 | Monthly recurring |
| OpenProxyAI Growth | $7,500.00 | Monthly recurring |

After creating each product, copy the **Price ID** (starts with `price_`).

## 3. Get your API keys

Dashboard → **Developers** → **API keys**:
- Copy the **Secret key** (`sk_test_...` for test, `sk_live_...` for production)

## 4. Configure the webhook endpoint

Dashboard → **Developers** → **Webhooks** → **Add endpoint**:

**Endpoint URL:**
```
https://openproxyai-backend-ikcideatha-nn.a.run.app/api/v1/billing/webhook
```
(Or your custom domain if configured.)

**Events to listen for:**
- `checkout.session.completed`
- `invoice.paid`
- `invoice.payment_failed`
- `customer.subscription.updated`
- `customer.subscription.deleted`

After saving, copy the **Signing secret** (`whsec_...`).

## 5. Add to your .env

```bash
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_STARTER_PRICE_ID=price_...
STRIPE_GROWTH_PRICE_ID=price_...
```

## 6. Local development — test webhooks

Install the [Stripe CLI](https://stripe.com/docs/stripe-cli) and forward events to your local server:

```bash
stripe listen --forward-to localhost:8000/api/v1/billing/webhook
```

The CLI prints a local webhook signing secret — use that as `STRIPE_WEBHOOK_SECRET` in development (it's different from the dashboard one).

To trigger test events:
```bash
stripe trigger checkout.session.completed
stripe trigger invoice.payment_failed
stripe trigger customer.subscription.deleted
```

## 7. Production checklist

Before going live, verify:

1. **Webhook URL (production)** — Use your live backend URL:
   ```
   https://openproxyai-backend-ikcideatha-nn.a.run.app/api/v1/billing/webhook
   ```
   Or your custom domain if configured. Create a separate webhook endpoint for production in the Stripe dashboard and copy its signing secret.

2. **Redirect URLs** — Set `STRIPE_SUCCESS_URL` and `STRIPE_CANCEL_URL` to your admin console billing page:
   ```bash
   STRIPE_SUCCESS_URL=https://admin-console-ecru.vercel.app/billing?success=1
   STRIPE_CANCEL_URL=https://admin-console-ecru.vercel.app/billing?canceled=1
   ```
   Replace with your actual admin-console URL if different.

3. **GitHub secrets** — For CI/CD deployments, add all Stripe env vars as GitHub secrets so they are passed to Cloud Run.

## 8. Test mode vs. production

- Use `sk_test_` keys during development — no real charges are made
- Use `sk_live_` keys in production only
- Never commit either key to git — use `.env` files only
- The app validates that live keys are not used in development (APP_ENV check)

## 9. Enterprise plans

Enterprise ($25,000+/mo) is handled manually — no Stripe price ID required. Set `org.plan = "enterprise"` directly via the admin API after confirming the contract.

## 10. Usage-based metered plan (optional)

Create a **metered** price in Stripe (per-unit usage, aggregate usage = **sum**) for token billing. Optionally add a fixed recurring **base** price on the same subscription.

**Environment variables:**

```bash
STRIPE_METERED_PRICE_ID=price_...           # required for metered checkout + usage sync
STRIPE_METERED_BASE_PRICE_ID=price_...      # optional second line item (e.g. platform fee)
METERED_SYNC_ENABLED=true                   # set false to disable hourly usage reporting job
METERED_INCLUDED_TOKENS_MONTHLY=1000000     # included allowance shown in admin UI / org API
```

The backend reports **hourly** token totals from `request_logs` to Stripe using idempotent usage records (`opai-meter-{org_id}-{YYYYMMDDHH}`). The job is a **sidecar**: failures are logged and never crash the API process.
