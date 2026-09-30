// Limits mirror PLAN_FEATURES in backend/app/config.py; prices from docs/features.md.
export interface Plan { id: string; name: string; price: string; users: string; retention: string; features: string[] }

export const PLANS: readonly Plan[] = [
  { id: 'free', name: 'Free', price: '$0', users: '3 users', retention: '7-day audit retention', features: ['5 API keys', 'OpenAI-compatible gateway', 'Budgets and rate limits'] },
  { id: 'starter', name: 'Starter', price: '$2,500/mo', users: '50 users', retention: '30-day audit retention', features: ['50 API keys', 'PII detection and redaction', 'Policy engine'] },
  { id: 'growth', name: 'Growth', price: '$7,500/mo', users: '200 users', retention: '90-day audit retention', features: ['200 API keys', 'Everything in Starter', 'Team budgets and chargeback'] },
  { id: 'enterprise', name: 'Enterprise', price: 'Custom', users: 'Unlimited users', retention: '365-day audit retention', features: ['Unlimited API keys', 'OIDC single sign-on', 'Customer-cluster or air-gapped install'] },
];
