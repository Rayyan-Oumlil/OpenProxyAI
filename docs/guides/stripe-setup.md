# Stripe Setup Guide

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
https://your-domain.com/api/v1/billing/webhook
```

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

## 7. Test mode vs. production

- Use `sk_test_` keys during development — no real charges are made
- Use `sk_live_` keys in production only
- Never commit either key to git — use `.env` files only
- The app validates that live keys are not used in development (APP_ENV check)

## 8. Enterprise plans

Enterprise ($25,000+/mo) is handled manually — no Stripe price ID required. Set `org.plan = "enterprise"` directly via the admin API after confirming the contract.
