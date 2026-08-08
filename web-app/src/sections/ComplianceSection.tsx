import { PAGE_MAX_WIDTH } from '../lib/layout';

const TEMPLATES = [
  { name: 'Healthcare', tag: 'HIPAA-aligned', desc: 'PHI redaction defaults, model allowlists for clinical data, extended audit retention.' },
  { name: 'Finance', tag: 'PCI-aligned', desc: 'Cardholder data blocking, transaction-context logging, stricter rate limits by default.' },
  { name: 'Government', tag: 'FedRAMP-aligned', desc: 'Air-gapped deployment support, data residency enforcement, 7-year retention.' },
];

const CAPABILITIES = [
  { title: 'Immutable audit trail', desc: 'Every request, response, and policy decision is logged and replay-able. Nothing is edited or deleted after the fact.' },
  { title: 'Org-level data isolation', desc: 'Every database query is scoped to your organization at the row level — no query can accidentally return another org’s data.' },
  { title: 'Data residency controls', desc: 'Route requests only through provider keys in approved regions, enforced at request time.' },
];

export default function ComplianceSection() {
  return (
    <section style={{ padding: '60px 0', borderTop: '1px solid var(--line)' }}>
      <div style={{ maxWidth: PAGE_MAX_WIDTH, margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr auto', gap: 24, alignItems: 'baseline', marginBottom: 32, paddingBottom: 12, borderBottom: '1px dashed var(--line)' }} className="sec-head">
          <span style={{ color: 'var(--ink-3)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.2em' }}>§01 · compliance</span>
          <h2 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(26px,2.8vw,38px)', letterSpacing: '-0.025em', fontWeight: 500, margin: 0, color: 'var(--ink)' }}>
            Built for the audit you'll <em style={{ fontStyle: 'normal', color: 'var(--accent)' }}>actually get.</em>
          </h2>
          <span style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.2em' }}>policy templates · not certifications</span>
        </div>

        <p style={{ color: 'var(--ink-2)', fontSize: 14, lineHeight: 1.7, maxWidth: '68ch', margin: '0 0 28px' }}>
          These are pre-built policy templates you configure and enforce yourself — a starting point aligned to common framework requirements, not a claim that OpenProxyAI itself holds a given certification. Your own audit still runs against your own controls.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10, marginBottom: 32 }} className="tri-grid">
          {TEMPLATES.map(t => (
            <div key={t.name} className="opa-card" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: 'var(--ink)', fontSize: 14, fontWeight: 500 }}>{t.name}</span>
                <span style={{ fontSize: 10.5, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{t.tag}</span>
              </div>
              <p style={{ color: 'var(--ink-2)', fontSize: 13, lineHeight: 1.6, margin: 0 }}>{t.desc}</p>
            </div>
          ))}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10 }} className="tri-grid">
          {CAPABILITIES.map(c => (
            <div key={c.title} style={{ padding: 18, border: '1px solid var(--line)', borderRadius: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <span style={{ color: 'var(--ink)', fontSize: 13, fontWeight: 500 }}>{c.title}</span>
              <p style={{ color: 'var(--ink-2)', fontSize: 13, lineHeight: 1.6, margin: 0 }}>{c.desc}</p>
            </div>
          ))}
        </div>
      </div>

      <style>{`
        @media (max-width: 1000px) {
          .sec-head { grid-template-columns: 1fr !important; }
          .tri-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </section>
  );
}
