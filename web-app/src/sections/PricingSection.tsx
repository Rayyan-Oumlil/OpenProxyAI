import Section from '../components/Section';
import { PLANS, yesNo } from '../lib/plans';

export default function PricingSection() {
  return (
    <Section id="plans" label="Plans" title={<>Four plans, <em>one product.</em></>} aside="what the software enforces">
      <div className="grid-4" style={{ marginBottom: 28 }}>
        {PLANS.map(p => (
          <div key={p.name} className="opa-card" style={{ padding: 26, display: 'flex', flexDirection: 'column', gap: 14, borderColor: p.featured ? 'var(--ink)' : undefined, boxShadow: p.featured ? '0 0 0 1px var(--ink)' : undefined }}>
            <h3 style={{ margin: 0, fontSize: 14, color: 'var(--ink-3)', fontWeight: 400, fontFamily: 'var(--mono)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{p.name}</h3>
            <div style={{ fontFamily: 'var(--sans)', fontSize: 34, letterSpacing: '-0.02em', fontWeight: 500, color: 'var(--ink)' }}>
              {p.price}<small style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--ink-3)', marginLeft: 4 }}>{p.period}</small>
            </div>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 8, fontSize: 15, color: 'var(--ink-2)' }}>
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
        <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 16, lineHeight: 1.6, color: 'var(--ink-2)' }}>
          The software limits only what the cards above show. Policy enforcement, protection by sensitivity, AI agent controls, budgets and limits, answer reuse, failover, the audit trail and monitoring export are not behind a paid tier.
        </p>
      </div>
      <p className="note">
        OpenProxyAI runs in your own environment, and paid plans are arranged directly with us. AI usage is billed by your model providers, never by OpenProxyAI.
      </p>
    </Section>
  );
}
