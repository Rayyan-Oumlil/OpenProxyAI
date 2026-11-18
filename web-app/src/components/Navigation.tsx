import { useEffect, useState } from 'react';
import { Menu, X } from 'lucide-react';
import { Link } from 'react-router-dom';
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

const linkStyle = { fontSize: 15, minHeight: 44, display: 'flex', alignItems: 'center' } as const;

export default function Navigation() {
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setMobileOpen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [mobileOpen]);

  return (
    <header style={{ position: 'sticky', top: 12, zIndex: 30, padding: '12px 24px 0' }}>
      <div style={{ maxWidth: 1240, margin: '0 auto', background: 'rgba(255,255,255,0.85)', WebkitBackdropFilter: 'blur(14px)', backdropFilter: 'blur(14px)', border: '1px solid var(--line)', borderRadius: 18 }}>
        <div className="nav-inner" style={{ padding: '8px 10px 8px 22px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 20 }}>
          <Link to="/" aria-label="OpenProxyAI home" style={{ textDecoration: 'none', minHeight: 44, display: 'flex', alignItems: 'center' }}><Logo /></Link>

          <nav className="navlinks" aria-label="Main" style={{ display: 'flex', gap: 26, alignItems: 'center' }}>
            {NAV_LINKS.map(l => l.external
              ? <a key={l.label} className="navlink" href={l.href} target="_blank" rel="noopener noreferrer" style={linkStyle}>{l.label}</a>
              : <Link key={l.label} className="navlink" to={l.href} style={linkStyle}>{l.label}</Link>)}
            <CommandPalette />
          </nav>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <a className="btn-p nav-cta" href={CALENDLY_URL} target="_blank" rel="noopener noreferrer" data-track="cta_book_demo" style={{ fontSize: 14, padding: '0 18px', minHeight: 44 }}>Book a demo</a>
            <button className="navtoggle" onClick={() => setMobileOpen(!mobileOpen)}
              aria-label={mobileOpen ? 'Close menu' : 'Open menu'} aria-expanded={mobileOpen} aria-controls="mobile-menu"
              style={{ background: 'none', border: 'none', color: 'var(--ink)', cursor: 'pointer', padding: 8, minHeight: 44 }}>
              {mobileOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>

        {mobileOpen && (
          <div id="mobile-menu" style={{ borderTop: '1px solid var(--line)', padding: '12px 22px 16px', display: 'flex', flexDirection: 'column' }}>
            {NAV_LINKS.map(l => l.external
              ? <a key={l.label} className="navlink" href={l.href} style={linkStyle}>{l.label}</a>
              : <Link key={l.label} className="navlink" to={l.href} onClick={() => setMobileOpen(false)} style={linkStyle}>{l.label}</Link>)}
          </div>
        )}
      </div>
    </header>
  );
}
