import { PAGE_MAX_WIDTH } from '../lib/layout';
import { APP_URL, CALENDLY_URL } from '../lib/links';

const PLANS = [
  {
    name: 'free_trial',
    price: '$0', period: '/ 14d',
    features: ['10K requests','10 users','all features','email support'],
    cta: '$ start →', href: APP_URL, featured: false,
  },
  {
    name: 'starter',
    price: '$2,500', period: '/ mo',
    features: ['100K req/mo','50 users','SSO','90-day retention'],
    cta: '$ demo', href: CALENDLY_URL, featured: false,
  },
  {
    name: 'growth',
    price: '$7,500', period: '/ mo',
    features: ['200 users','policy + DLP','SCIM','1yr retention'],
    cta: '$ demo →', href: CALENDLY_URL, featured: true,
  },
  {
    name: 'enterprise',
    price: 'custom', period: '',
    features: ['unlimited','air-gapped / on-prem','7yr retention','99.99% SLA'],
    cta: '$ contact', href: CALENDLY_URL, featured: false,
  },
];

export default function PricingSection() {
  return (
    <section style={{ padding: '60px 0', borderTop: '1px solid var(--line)' }}>
      <div style={{ maxWidth: PAGE_MAX_WIDTH, margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr auto', gap: 24, alignItems: 'baseline', marginBottom: 32, paddingBottom: 12, borderBottom: '1px dashed var(--line)' }} className="sec-head">
          <span style={{ color: 'var(--ink-3)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.2em' }}>§05 · pricing</span>
          <h2 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(26px,2.8vw,38px)', letterSpacing: '-0.025em', fontWeight: 500, margin: 0, color: 'var(--ink)' }}>
            Flat fee. <em style={{ fontStyle: 'normal', color: 'var(--accent)' }}>No token surprises.</em> Start free.
          </h2>
          <span style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.2em' }}>14-day trial · no card</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10, marginBottom: 32 }} className="price-grid">
          {PLANS.map(p => (
            <div key={p.name} style={{
              padding: 20, border: `1px solid ${p.featured ? 'var(--accent)' : 'var(--line)'}`,
              borderRadius: 10,
              background: p.featured ? 'color-mix(in srgb, var(--accent) 5%, var(--panel))' : 'var(--panel)',
              display: 'flex', flexDirection: 'column', gap: 10,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <h3 style={{ margin: 0, fontSize: 13, color: 'var(--ink-2)', fontWeight: 400 }}>{p.name}</h3>
                {p.featured && (
                  <span style={{ background: 'var(--accent)', color: 'var(--bg)', padding: '1px 6px', borderRadius: 3, fontSize: 10 }}>popular</span>
                )}
              </div>
              <div style={{ fontFamily: 'var(--sans)', fontSize: 28, letterSpacing: '-0.02em', fontWeight: 500, color: 'var(--ink)' }}>
                {p.price}
                {p.period && <small style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--ink-3)', marginLeft: 4 }}>{p.period}</small>}
              </div>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12, color: 'var(--ink-2)' }}>
                {p.features.map(f => (
                  <li key={f} style={{ display: 'flex', gap: 8 }}>
                    <span style={{ color: 'var(--accent)' }}>›</span>{f}
                  </li>
                ))}
              </ul>
              <a
                href={p.href}
                target={p.href === APP_URL ? undefined : '_blank'}
                rel={p.href === APP_URL ? undefined : 'noopener noreferrer'}
                className={p.featured ? 'opa-btn opa-btn-primary' : 'opa-btn'}
                style={{ marginTop: 'auto' }}
              >{p.cta}</a>
            </div>
          ))}
        </div>

        {/* Deploy CTA */}
        <div style={{
          padding: 36,
          border: '1px solid var(--accent)',
          background: 'radial-gradient(ellipse 60% 100% at 90% 50%, color-mix(in srgb, var(--accent) 15%, transparent) 0%, transparent 70%), var(--panel)',
          borderRadius: 12,
          display: 'grid', gridTemplateColumns: '1fr auto', gap: 24, alignItems: 'center',
        }} className="cta-grid">
          <div>
            <h2 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(26px,3vw,42px)', letterSpacing: '-0.025em', fontWeight: 500, margin: 0, color: 'var(--ink)' }}>
              Stop shipping AI <em style={{ fontStyle: 'normal', color: 'var(--accent)' }}>blind.</em>
            </h2>
            <p style={{ color: 'var(--ink-2)', fontFamily: 'var(--sans)', fontSize: 14, margin: '8px 0 0', maxWidth: '60ch' }}>
              Deploy in your VPC. Keep your provider keys. Get the audit trail your legal team actually asked for — in under an hour.
            </p>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <a href={APP_URL} className="opa-btn opa-btn-primary">$ start trial →</a>
            <a href={CALENDLY_URL} target="_blank" rel="noopener noreferrer" className="opa-btn">$ talk sales</a>
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 1000px) {
          .price-grid { grid-template-columns: repeat(2,1fr) !important; }
          .cta-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </section>
  );
}
