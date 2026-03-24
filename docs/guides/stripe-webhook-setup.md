# Stripe Webhook — Quick Setup

Use this when you're ready to enable paid plans. Your backend URL:

```
https://openproxyai-backend-ikcideatha-nn.a.run.app
```

## 1. Stripe Dashboard → Webhooks

[Stripe Dashboard → Developers → Webhooks](https://dashboard.stripe.com/webhooks) → **Add endpoint**

| Field | Value |
|-------|-------|
| **Endpoint URL** | `https://openproxyai-backend-ikcideatha-nn.a.run.app/api/v1/billing/webhook` |
| **Events** | `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted` |

Click **Add endpoint**. Copy the **Signing secret** (`whsec_...`).

## 2. Add GitHub Secrets

GitHub → repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these (get values from Stripe Dashboard → Developers → API keys, Products):

| Secret name | Value |
|-------------|-------|
| `STRIPE_SECRET_KEY` | `sk_test_...` or `sk_live_...` |
| `STRIPE_PUBLISHABLE_KEY` | `pk_test_...` or `pk_live_...` |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` (from step 1) |
| `STRIPE_STARTER_PRICE_ID` | `price_...` (from Products) |
| `STRIPE_GROWTH_PRICE_ID` | `price_...` |
| `STRIPE_SUCCESS_URL` | `https://admin-console-ecru.vercel.app/billing?success=1` |
| `STRIPE_CANCEL_URL` | `https://admin-console-ecru.vercel.app/billing?canceled=1` |

## 3. Redeploy

Push to `main` or manually re-run the deploy workflow. The new env vars will be picked up.

## 4. Test

Create a test checkout from the admin console billing page. Use Stripe test card `4242 4242 4242 4242` if in test mode.

---

Full guide: [stripe-setup.md](./stripe-setup.md)
