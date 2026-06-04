import { useState } from 'react';
import { Menu, X } from 'lucide-react';

const STATUS_CHIPS = [
  { label: 'us-east-1 · healthy', dot: 'ok' },
  { label: 'eu-west-1 · healthy', dot: 'ok' },
  { label: 'ap-south-1 · degraded', dot: 'warn' },
  { label: 'p95 812ms', dot: null },
  { label: 'cache 41.3%', dot: null },
];

const NAV_LINKS = ['proxy', 'policies', 'playground', 'console', 'docs', 'status'];

function StatusDot({ kind }: { kind: 'ok' | 'warn' | null }) {
  if (!kind) return null;
  const color = kind === 'ok' ? 'var(--accent)' : 'var(--warn)';
  return (
    <span style={{
      display: 'inline-block', width: 6, height: 6, borderRadius: '50%',
      background: color, boxShadow: `0 0 0 3px color-mix(in srgb, ${color} 25%, transparent)`,
      marginRight: 8, flexShrink: 0,
    }} />
  );
}

export default function Navigation() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const today = new Date().toISOString().slice(0, 10);

  return (
    <header>
      {/* Top rail */}
      <div style={{ borderBottom: '1px solid var(--line)', background: 'var(--bg-2)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.15em', color: 'var(--ink-3)' }}>
        <div style={{ maxWidth: 1380, margin: '0 auto', padding: '8px 24px', display: 'grid', gridTemplateColumns: 'auto 1fr auto', gap: 24, alignItems: 'center' }}>
          <span><strong style={{ color: 'var(--ink)' }}>openproxy.ai</strong>{' · control plane'}</span>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' as const }}>
            {STATUS_CHIPS.map((c, i) => (
              <span key={i} style={{ display: 'inline-flex', alignItems: 'center' }}>
                <StatusDot kind={c.dot as 'ok' | 'warn' | null} />
                {c.label}
              </span>
            ))}
          </div>
          <span>build 2.4.1 · {today}</span>
        </div>
      </div>

      {/* Nav bar */}
      <nav style={{ borderBottom: '1px solid var(--line)', background: 'var(--bg)' }}>
        <div style={{ maxWidth: 1380, margin: '0 auto', padding: '0 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 60 }}>
          <a href="#" style={{ display: 'flex', alignItems: 'center', gap: 12, textDecoration: 'none', color: 'var(--ink)', fontWeight: 600, fontSize: 15, letterSpacing: '-0.01em' }}>
            <span style={{ width: 24, height: 24, borderRadius: 4, background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--bg)', fontSize: 11, fontWeight: 700 }}>/</span>
            OpenProxyAI
          </a>

          <ul style={{ listStyle: 'none', margin: 0, padding: 0, gap: 22, fontSize: 13, display: 'flex' }} className="hidden lg:flex">
            {NAV_LINKS.map(l => (
              <li key={l}>
                <a href="#" style={{ color: 'var(--ink-2)', textDecoration: 'none', transition: 'color 0.12s' }}
                  onMouseEnter={e => (e.currentTarget.style.color = 'var(--accent)')}
                  onMouseLeave={e => (e.currentTarget.style.color = 'var(--ink-2)')}>
                  {l}
                </a>
              </li>
            ))}
          </ul>

          <div style={{ display: 'flex', gap: 8 }} className="hidden lg:flex">
            <a href="#" className="opa-btn">$ sign in</a>
            <a href="#" className="opa-btn opa-btn-primary">$ book demo →</a>
          </div>

          <button className="lg:hidden" onClick={() => setMobileOpen(!mobileOpen)}
            style={{ background: 'none', border: 'none', color: 'var(--ink)', cursor: 'pointer', padding: 4 }}>
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        {mobileOpen && (
          <div style={{ borderTop: '1px solid var(--line)', padding: '16px 24px', display: 'flex', flexDirection: 'column', gap: 12 }}>
            {NAV_LINKS.map(l => <a key={l} href="#" style={{ color: 'var(--ink-2)', textDecoration: 'none', fontSize: 14 }}>{l}</a>)}
            <div style={{ display: 'flex', gap: 8, paddingTop: 8, borderTop: '1px solid var(--line)' }}>
              <a href="#" className="opa-btn">$ sign in</a>
              <a href="#" className="opa-btn opa-btn-primary">$ book demo →</a>
            </div>
          </div>
        )}
      </nav>
    </header>
  );
}
