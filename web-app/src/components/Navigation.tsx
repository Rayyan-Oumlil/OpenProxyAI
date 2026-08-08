import { useState } from 'react';
import { Menu, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import { PAGE_MAX_WIDTH } from '../lib/layout';

const NAV_LINKS = [
  { label: 'product', href: '/product', external: false },
  { label: 'security', href: '/security', external: false },
  { label: 'providers', href: '/providers', external: false },
  { label: 'pricing', href: '/pricing', external: false },
  { label: 'docs', href: 'https://docs.openproxy.ai', external: true },
];

export default function Navigation() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header>
      {/* Nav bar */}
      <nav style={{ borderBottom: '1px solid var(--line)', background: 'var(--bg)' }}>
        <div style={{ maxWidth: PAGE_MAX_WIDTH, margin: '0 auto', padding: '0 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 60 }}>
          <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 12, textDecoration: 'none', color: 'var(--ink)', fontWeight: 600, fontSize: 15, letterSpacing: '-0.01em' }}>
            <span style={{ width: 24, height: 24, borderRadius: 4, background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--bg)', fontSize: 11, fontWeight: 700 }}>/</span>
            OpenProxyAI
          </Link>

          <ul style={{ listStyle: 'none', margin: 0, padding: 0, gap: 22, fontSize: 13, display: 'flex' }} className="hidden lg:flex">
            {NAV_LINKS.map(l => (
              <li key={l.label}>
                {l.external ? (
                  <a href={l.href} style={{ color: 'var(--ink-2)', textDecoration: 'none', transition: 'color 0.12s' }}
                    onMouseEnter={e => (e.currentTarget.style.color = 'var(--accent)')}
                    onMouseLeave={e => (e.currentTarget.style.color = 'var(--ink-2)')}>
                    {l.label}
                  </a>
                ) : (
                  <Link to={l.href} style={{ color: 'var(--ink-2)', textDecoration: 'none', transition: 'color 0.12s' }}
                    onMouseEnter={e => (e.currentTarget.style.color = 'var(--accent)')}
                    onMouseLeave={e => (e.currentTarget.style.color = 'var(--ink-2)')}>
                    {l.label}
                  </Link>
                )}
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
            {NAV_LINKS.map(l => l.external
              ? <a key={l.label} href={l.href} style={{ color: 'var(--ink-2)', textDecoration: 'none', fontSize: 14 }}>{l.label}</a>
              : <Link key={l.label} to={l.href} style={{ color: 'var(--ink-2)', textDecoration: 'none', fontSize: 14 }}>{l.label}</Link>)}
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
