import { CALENDLY_URL, docsPage } from './links';

export interface Plan {
  name: string;
  price: string;
  period: string;
  users: string;
  keys: string;
  pii: boolean;
  sso: boolean;
  retention: string;
  cta: string;
  href: string;
  featured?: boolean;
}

// Limits mirror PLAN_FEATURES in backend/app/config.py; prices mirror docs/guides/stripe-setup.md.
export const PLANS: Plan[] = [
  { name: 'community', price: '$0', period: 'forever', users: '3', keys: '5', pii: false, sso: false, retention: '7 days', cta: 'Get started', href: docsPage('/getting-started/quickstart') },
  { name: 'team', price: '$299', period: '/ month', users: '50', keys: '50', pii: true, sso: false, retention: '30 days', cta: 'Book a call', href: CALENDLY_URL },
  { name: 'business', price: '$1,500', period: '/ month', users: '200', keys: '200', pii: true, sso: false, retention: '90 days', cta: 'Book a call', href: CALENDLY_URL, featured: true },
  { name: 'enterprise', price: 'from $25k', period: '/ year', users: 'unlimited', keys: 'unlimited', pii: true, sso: true, retention: '365 days', cta: 'Book a call', href: CALENDLY_URL },
];

export const yesNo = (value: boolean): string => (value ? 'yes' : 'no');
