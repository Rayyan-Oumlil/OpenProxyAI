import Section from '../components/Section';
import { CALENDLY_URL, docsPage } from '../lib/links';

interface Plan {
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
const PLANS: Plan[] = [
  { name: 'community', price: '$0', period: 'forever', users: '3', keys: '5', pii: false, sso: false, retention: '7 days', cta: 'Get started', href: docsPage('/getting-started/quickstart') },
  { name: 'team', price: '$299', period: '/ month', users: '50', keys: '50', pii: true, sso: false, retention: '30 days', cta: 'Book a call', href: CALENDLY_URL },
  { name: 'business', price: '$1,500', period: '/ month', users: '200', keys: '200', pii: true, sso: false, retention: '90 days', cta: 'Book a call', href: CALENDLY_URL, featured: true },
  { name: 'enterprise', price: 'from $25k', period: '/ year', users: 'unlimited', keys: 'unlimited', pii: true, sso: true, retention: '365 days', cta: 'Book a call', href: CALENDLY_URL },
];

const yesNo = (value: boolean): string => (value ? 'yes' : 'no');

export default function PricingSection() {
  return (
    <Section id="plans" label="Plans" title={<>Four plans, <em>one product.</em></>} aside="what the software enforces">
      <div className="grid-4" style={{ marginBottom: 28 }}>
        {PLANS.map(p => (
          <div key={p.name} className="opa-card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 12, borderColor: p.featured ? 'var(--accent)' : undefined }}>
            <h3 style={{ margin: 0, fontSize: 13, color: 'var(--ink-2)', fontWeight: 400 }}>{p.name}</h3>
            <div style={{ fontFamily: 'var(--sans)', fontSize: 28, letterSpacing: '-0.02em', fontWeight: 500, color: 'var(--ink)' }}>
              {p.price}<small style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--ink-3)', marginLeft: 4 }}>{p.period}</small>
            </div>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12, color: 'var(--ink-2)' }}>
              <li>› {p.users} users · {p.keys} access keys</li>
              <li>› {p.retention} of audit history</li>
              <li>› Personal-data settings and compliance templates: {yesNo(p.pii)}</li>
              <li>› Single sign-on and user provisioning: {yesNo(p.sso)}</li>
            </ul>
            <a
              href={p.href}
              {...(p.href.startsWith('http') ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
              className={p.featured ? 'opa-btn opa-btn-primary' : 'opa-btn'}
              style={{ marginTop: 'auto' }}
              data-track={`cta_plan_${p.name}`}
            >{p.cta}</a>
          </div>
        ))}
      </div>

      <div className="opa-card" style={{ padding: 22 }}>
        <div style={{ color: 'var(--ink)', fontSize: 14, fontWeight: 500, marginBottom: 8 }}>The same on every plan</div>
        <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 14, lineHeight: 1.65, color: 'var(--ink-2)' }}>
          The software limits only what the cards above show. Policy enforcement, protection by sensitivity, AI agent controls, budgets and limits, answer reuse, failover, the audit trail and monitoring export are not behind a paid tier.
        </p>
      </div>
      <p className="note">
        OpenProxyAI runs in your own environment: there is no hosted service and no online checkout today. Paid plans are arranged directly. AI usage is billed by your model providers, never by OpenProxyAI.
      </p>
    </Section>
  );
}
