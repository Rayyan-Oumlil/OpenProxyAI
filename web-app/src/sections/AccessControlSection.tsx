import { PAGE_MAX_WIDTH } from '../lib/layout';

const CONTROLS = [
  { layer: 'identity', title: 'SSO / SAML / OIDC', desc: 'Connect your identity provider so org members sign in through it instead of a password — enforced org-wide, not opt-in per user.' },
  { layer: 'key & budget', title: 'Team-scoped roles', desc: 'API keys and budgets are scoped to a team by default. A key can only spend against the budget and call the models its team is allowed to use.' },
  { layer: 'membership', title: 'Invite-based provisioning', desc: 'New members are added by email invite, not shared credentials — access is revoked by removing the member, not rotating a shared key everyone used.' },
];

export default function AccessControlSection() {
  return (
    <section style={{ padding: '60px 0', borderTop: '1px solid var(--line)' }}>
      <div style={{ maxWidth: PAGE_MAX_WIDTH, margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr auto', gap: 24, alignItems: 'baseline', marginBottom: 40, paddingBottom: 12, borderBottom: '1px dashed var(--line)' }} className="sec-head">
          <span style={{ color: 'var(--ink-3)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.2em' }}>§03 · access control</span>
          <h2 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(26px,2.8vw,38px)', letterSpacing: '-0.025em', fontWeight: 500, margin: 0, color: 'var(--ink)' }}>
            Who can do what, <em style={{ fontStyle: 'normal', color: 'var(--accent)' }}>enforced at every layer.</em>
          </h2>
          <span style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.2em' }}>growth + enterprise</span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', maxWidth: 760 }}>
          {CONTROLS.map((c, i) => (
            <div key={c.title}>
              <div style={{
                display: 'grid', gridTemplateColumns: '110px 1fr', gap: 20,
                padding: '18px 20px', border: '1px solid var(--line)', borderRadius: 8,
                background: 'var(--panel)', alignItems: 'center',
              }} className="layer-row">
                <span style={{ color: 'var(--accent)', fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.12em' }}>{c.layer}</span>
                <div>
                  <div style={{ color: 'var(--ink)', fontSize: 13.5, fontWeight: 500, marginBottom: 4 }}>{c.title}</div>
                  <div style={{ color: 'var(--ink-2)', fontSize: 13, lineHeight: 1.6 }}>{c.desc}</div>
                </div>
              </div>
              {i < CONTROLS.length - 1 && (
                <div style={{ display: 'flex', justifyContent: 'flex-start', padding: '2px 0 2px 55px' }}>
                  <span style={{ color: 'var(--line-2)', fontSize: 14, lineHeight: 1 }}>│</span>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <style>{`
        @media (max-width: 1000px) {
          .sec-head { grid-template-columns: 1fr !important; }
          .layer-row { grid-template-columns: 1fr !important; gap: 6px !important; }
        }
      `}</style>
    </section>
  );
}
