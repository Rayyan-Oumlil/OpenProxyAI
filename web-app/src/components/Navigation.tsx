import { useEffect, useState } from 'react';
import { Menu, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import { PAGE_MAX_WIDTH } from '../lib/layout';
import { CALENDLY_URL, DOCS_URL, GITHUB_URL } from '../lib/links';
import CommandPalette from './CommandPalette';
import Logo from './Logo';

const NAV_LINKS = [
  { label: 'Product', href: '/product', external: false },
  { label: 'Security', href: '/security', external: false },
  { label: 'Integrations', href: '/providers', external: false },
  { label: 'Compare', href: '/compare', external: false },
  { label: 'Pricing', href: '/pricing', external: false },
  { label: 'Docs', href: DOCS_URL, external: true },
  { label: 'GitHub', href: GITHUB_URL, external: true },
];

export default function Navigation() {
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [mobileOpen]);

  return (
    <header>
      {/* Nav bar */}
      <nav style={{ borderBottom: '1px solid var(--line)', background: 'var(--bg)' }}>
        <div style={{ maxWidth: PAGE_MAX_WIDTH, margin: '0 auto', padding: '0 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 60 }}>
          <Link to="/" aria-label="OpenProxyAI home" style={{ textDecoration: 'none' }}><Logo /></Link>

          <div style={{ alignItems: 'center', gap: 28 }} className="hidden lg:flex">
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, gap: 22, fontSize: 14, display: 'flex' }}>
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
          <CommandPalette />
          </div>

          <div style={{ gap: 8 }} className="hidden lg:flex">
            <a href={CALENDLY_URL} target="_blank" rel="noopener noreferrer" className="opa-btn opa-btn-primary" data-track="cta_book_demo">Book a demo</a>
          </div>

          <button className="lg:hidden" onClick={() => setMobileOpen(!mobileOpen)}
            aria-label={mobileOpen ? 'Close menu' : 'Open menu'} aria-expanded={mobileOpen} aria-controls="mobile-menu"
            style={{ background: 'none', border: 'none', color: 'var(--ink)', cursor: 'pointer', padding: 4 }}>
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        {mobileOpen && (
          <div id="mobile-menu" style={{ borderTop: '1px solid var(--line)', padding: '16px 24px', display: 'flex', flexDirection: 'column', gap: 12 }}>
            {NAV_LINKS.map(l => l.external
              ? <a key={l.label} href={l.href} style={{ color: 'var(--ink-2)', textDecoration: 'none', fontSize: 14 }}>{l.label}</a>
              : <Link key={l.label} to={l.href} onClick={() => setMobileOpen(false)} style={{ color: 'var(--ink-2)', textDecoration: 'none', fontSize: 14 }}>{l.label}</Link>)}
            <div style={{ display: 'flex', gap: 8, paddingTop: 8, borderTop: '1px solid var(--line)' }}>
              <a href={CALENDLY_URL} target="_blank" rel="noopener noreferrer" className="opa-btn opa-btn-primary" data-track="cta_book_demo">Book a demo</a>
            </div>
          </div>
        )}
      </nav>
    </header>
  );
}
