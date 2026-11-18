const ITEMS: Array<[string, string]> = [
  ['Chat assistants', 'M3 4.5h10v6.5H7.5L5 13.5V11H3z'],
  ['Coding assistants', 'M5.5 5L2.5 8l3 3M10.5 5l3 3-3 3'],
  ['AI agents', 'M3 5h10v8H3zM8 2.5V5M6 9h.01M10 9h.01'],
  ['Your internal apps', 'M2.5 3h11v10h-11zM2.5 6.5h11'],
  ['Hosted AI models', 'M8 2.5l1.4 4.1 4.1 1.4-4.1 1.4L8 13.5 6.6 9.4 2.5 8l4.1-1.4z'],
  ['Models you run yourself', 'M2.5 3h11v4h-11zM2.5 9h11v4h-11zM5 5h.01M5 11h.01'],
  ['The tools agents use', 'M3 5h10M3 11h10'],
];
const CLAIMS: Array<[string, boolean]> = [
  ['Sensitive data stays where it belongs', true],
  ['AI agents stay on approved tools', false],
  ['Everything is provable to auditors', true],
  ['Runs in your own environment', false],
];

const pill = { display: 'flex', alignItems: 'center', gap: 10, padding: '11px 20px', border: '1px solid var(--line-2)', borderRadius: 14, background: 'var(--bg-2)' } as const;

export default function MarqueeSection() {
  const copies = [0, 1];
  return (
    <div className="marqwrap" aria-hidden="true" style={{ borderTop: '1px solid var(--line)', borderBottom: '1px solid var(--line)', background: '#fff', overflow: 'hidden', padding: '30px 0', display: 'flex', flexDirection: 'column', gap: 26 }}>
      <div className="marq rev" data-marq="rev" style={{ fontSize: 15, fontWeight: 500, whiteSpace: 'nowrap' }}>
        {copies.map(c => (
          <div key={c} style={{ display: 'flex', alignItems: 'center', gap: 14, paddingRight: 14 }}>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 12, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--ink-3)', padding: '0 18px' }}>Sits in front of</span>
            {ITEMS.map(([label, d]) => (
              <span key={label} style={pill}>
                <svg width="18" height="18" viewBox="0 0 16 16" fill="none" stroke="var(--ink)" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
                {label}
              </span>
            ))}
          </div>
        ))}
      </div>
      <div className="marq" data-marq="fwd" style={{ fontSize: 'clamp(26px, 3.4vw, 46px)', fontWeight: 500, letterSpacing: '-0.03em', lineHeight: 1.1, whiteSpace: 'nowrap' }}>
        {copies.map(c => (
          <div key={c} style={{ display: 'flex', alignItems: 'center', gap: 44, paddingRight: 44 }}>
            {CLAIMS.map(([t, strong]) => (
              <span key={t} style={{ display: 'flex', alignItems: 'center', gap: 44 }}>
                <span style={{ color: strong ? 'var(--ink)' : 'var(--soft)' }}>{t}</span>
                <span style={{ color: 'var(--ink)' }}>+</span>
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
