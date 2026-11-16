import Section from '../components/Section';
import { CALENDLY_URL, repoFile } from '../lib/links';

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
  { name: 'community', price: '$0', period: 'forever', users: '3', keys: '5', pii: false, sso: false, retention: '7 days', cta: '$ run the demo', href: '/#try' },
  { name: 'team', price: '$299', period: '/ month', users: '50', keys: '50', pii: true, sso: false, retention: '30 days', cta: '$ talk to the author', href: CALENDLY_URL },
  { name: 'business', price: '$1,500', period: '/ month', users: '200', keys: '200', pii: true, sso: false, retention: '90 days', cta: '$ talk to the author', href: CALENDLY_URL, featured: true },
  { name: 'enterprise', price: 'from $25k', period: '/ year', users: 'unlimited', keys: 'unlimited', pii: true, sso: true, retention: '365 days', cta: '$ talk to the author', href: CALENDLY_URL },
];

const yesNo = (value: boolean): string => (value ? 'yes' : 'no');

export default function PricingSection() {
  return (
    <Section id="plans" label="§01 · plans" title={<>Four plans, <em>one codebase.</em></>} aside="what the software enforces">
      <div className="grid-4" style={{ marginBottom: 28 }}>
        {PLANS.map(p => (
          <div key={p.name} className="opa-card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 12, borderColor: p.featured ? 'var(--accent)' : undefined }}>
            <h3 style={{ margin: 0, fontSize: 13, color: 'var(--ink-2)', fontWeight: 400 }}>{p.name}</h3>
            <div style={{ fontFamily: 'var(--sans)', fontSize: 28, letterSpacing: '-0.02em', fontWeight: 500, color: 'var(--ink)' }}>
              {p.price}<small style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--ink-3)', marginLeft: 4 }}>{p.period}</small>
            </div>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12, color: 'var(--ink-2)' }}>
              <li>› {p.users} users · {p.keys} API keys</li>
              <li>› {p.retention} audit retention</li>
              <li>› PII settings and compliance templates: {yesNo(p.pii)}</li>
              <li>› SSO (OIDC) and SCIM: {yesNo(p.sso)}</li>
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
          The software gates only the limits in the cards above. Policy enforcement, data-class routing, the MCP gateway, budgets and rate limits, caching, failover, the audit trail and SIEM and OpenTelemetry export are not behind a paid tier in the code.{' '}
          <a href={repoFile('backend/app/config.py')} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>See PLAN_FEATURES →</a>
        </p>
      </div>
      <p className="note">
        OpenProxyAI is self-hosted: there is no hosted service and no self-serve checkout today. Paid plans are arranged directly. Provider tokens are billed by your model providers, never by OpenProxyAI.
      </p>
    </Section>
  );
}
