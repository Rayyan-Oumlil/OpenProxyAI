import { PAGE_MAX_WIDTH } from '../lib/layout';

const FAQS = [
  { q: 'Do you charge per token?', a: 'No — plans are flat monthly fees based on usage tier and seats. You still pay your model providers directly for tokens; OpenProxyAI doesn\'t mark those up.' },
  { q: 'What happens if we exceed our plan\'s request limit?', a: 'You\'re notified before hitting the ceiling. Overages are billed at a per-request rate rather than hard-stopping your traffic — contact sales if you need a hard cap instead.' },
  { q: 'Can we self-host instead of using a hosted plan?', a: 'Yes — Enterprise includes air-gapped and on-prem deployment. Starter and Growth are typically hosted but can be self-hosted on request.' },
  { q: 'Is there a discount for annual billing?', a: 'Yes, contact sales — annual commitments get a reduced effective rate versus month-to-month.' },
];

export default function PricingFaqSection() {
  return (
    <section style={{ padding: '60px 0', borderTop: '1px solid var(--line)' }}>
      <div style={{ maxWidth: PAGE_MAX_WIDTH, margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr auto', gap: 24, alignItems: 'baseline', marginBottom: 32, paddingBottom: 12, borderBottom: '1px dashed var(--line)' }} className="sec-head">
          <span style={{ color: 'var(--ink-3)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.2em' }}>§02 · faq</span>
          <h2 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(26px,2.8vw,38px)', letterSpacing: '-0.025em', fontWeight: 500, margin: 0, color: 'var(--ink)' }}>
            Billing, <em style={{ fontStyle: 'normal', color: 'var(--accent)' }}>plainly explained.</em>
          </h2>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {FAQS.map((f, i) => (
            <div key={f.q} style={{ padding: '14px 0', borderBottom: i < FAQS.length - 1 ? '1px solid var(--line)' : 'none' }}>
              <div style={{ color: 'var(--ink)', fontSize: 14, fontWeight: 500, marginBottom: 6 }}>{f.q}</div>
              <div style={{ color: 'var(--ink-2)', fontSize: 13, lineHeight: 1.6 }}>{f.a}</div>
            </div>
          ))}
        </div>
      </div>

      <style>{`
        @media (max-width: 1000px) {
          .sec-head { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </section>
  );
}
