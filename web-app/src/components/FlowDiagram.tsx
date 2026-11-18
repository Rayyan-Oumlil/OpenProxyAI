/** People, apps and agents pass through the checkpoint to approved models and tools; everything else is stopped. */
const chip = { display: 'flex', alignItems: 'center', gap: 8, padding: '9px 14px', background: '#fff', border: '1px solid var(--line-2)', borderRadius: 999, fontSize: 13, fontWeight: 500, lineHeight: 1.2, boxShadow: '0 10px 22px -14px rgba(28,27,24,0.4)' } as const;
const icon = { width: 16, height: 16, viewBox: '0 0 16 16', fill: 'none', stroke: 'var(--ink)', strokeWidth: 1.5, strokeLinecap: 'round', strokeLinejoin: 'round', style: { flex: 'none' } } as const;


export default function FlowDiagram() {
  return (
    <div role="img" aria-label="People, apps and AI agents pass through OpenProxyAI to reach approved models and approved tools. Everything else is stopped." style={{ position: 'relative', display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto minmax(0, 1fr)', alignItems: 'center', gap: 12, height: 230, margin: '4px clamp(0px, 3vw, 48px) clamp(18px, 3vw, 36px)' }}>
      <svg aria-hidden="true" viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
        {['M8 14 C 32 14, 30 50, 50 50', 'M8 50 L 50 50', 'M8 86 C 32 86, 30 50, 50 50', 'M50 50 C 70 50, 68 14, 92 14', 'M50 50 L 92 50'].map(d => (
          <path key={d} className="flow" d={d} fill="none" stroke="#1c1b18" strokeWidth="1.3" vectorEffect="non-scaling-stroke" />
        ))}
        <path d="M50 50 C 70 50, 68 86, 92 86" fill="none" stroke="#b3361f" strokeWidth="1.3" strokeDasharray="2 6" vectorEffect="non-scaling-stroke" />
      </svg>
      <div style={{ position: 'relative', height: '100%', padding: '12px 0', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <span className="chipf" style={chip}><svg {...icon}><circle cx="8" cy="5.5" r="2.5" /><path d="M3 14c0-2.8 2.2-4.5 5-4.5s5 1.7 5 4.5" /></svg>People</span>
        <span className="chipf c2" style={chip}><svg {...icon}><rect x="2.5" y="3" width="11" height="10" rx="2" /><path d="M2.5 6.5h11" /></svg>Apps</span>
        <span className="chipf c3" style={chip}><svg {...icon}><rect x="3" y="5" width="10" height="8" rx="2" /><path d="M8 2.5V5M6 9h.01M10 9h.01" /></svg>AI agents</span>
      </div>
      <div style={{ position: 'relative', width: 76, height: 76, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span className="ring" style={{ position: 'absolute', inset: 6, borderRadius: 22, border: '1px solid var(--ink)' }} />
        <span className="ring r2" style={{ position: 'absolute', inset: 6, borderRadius: 22, border: '1px solid var(--ink)' }} />
        <svg width="64" height="64" viewBox="0 0 26 26" aria-hidden="true" style={{ position: 'relative', filter: 'drop-shadow(0 12px 18px rgba(28,27,24,0.3))' }}>
          <rect width="26" height="26" rx="7" fill="#1c1b18" /><path d="M5 13h5.5M13 6v14" stroke="#fff" strokeWidth="2" strokeLinecap="round" fill="none" /><circle cx="18.5" cy="13" r="2.5" fill="#fff" />
        </svg>
      </div>
      <div style={{ position: 'relative', height: '100%', padding: '12px 0', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <span className="chipf c2" style={{ ...chip, borderColor: 'var(--ok-line)' }}><svg {...icon}><path d="M8 2.5l1.4 4.1 4.1 1.4-4.1 1.4L8 13.5 6.6 9.4 2.5 8l4.1-1.4z" /></svg>Approved models</span>
        <span className="chipf c3" style={{ ...chip, borderColor: 'var(--ok-line)' }}><svg {...icon}><path d="M3 5h10M3 11h10" /><circle cx="6" cy="5" r="1.6" fill="#fff" /><circle cx="10" cy="11" r="1.6" fill="#fff" /></svg>Approved tools</span>
        <span className="chipf" style={{ ...chip, background: 'var(--stop-bg)', borderColor: 'var(--stop-line)', color: 'var(--stop)', boxShadow: 'none' }}><svg {...icon} stroke="var(--stop)" strokeWidth={1.6}><circle cx="8" cy="8" r="6" /><path d="M4 12L12 4" /></svg>Everything else</span>
      </div>
    </div>
  );
}
