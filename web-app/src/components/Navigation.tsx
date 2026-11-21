import { useEffect, useRef, useState } from 'react';
import { ChevronDown, Menu, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import { CALENDLY_URL, DOCS_URL, GITHUB_URL } from '../lib/links';
import { SUB_PRODUCTS } from '../lib/subProducts';
import CommandPalette from './CommandPalette';
import Logo from './Logo';

const NAV_LINKS = [
  { label: 'Product', href: '/product', external: false, children: SUB_PRODUCTS },
  { label: 'Security', href: '/security', external: false },
  { label: 'Integrations', href: '/providers', external: false },
  { label: 'Compare', href: '/compare', external: false },
  { label: 'Pricing', href: '/pricing', external: false },
  { label: 'Docs', href: DOCS_URL, external: true },
  { label: 'GitHub', href: GITHUB_URL, external: true },
] as const;

const linkStyle = { fontSize: 15, minHeight: 44, display: 'flex', alignItems: 'center' } as const;

/** "Product" with its three products underneath. The label still goes to /product; the chevron opens the list. */
function ProductMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  // Choosing a link closes the menu and drops focus from it, so neither hover nor focus keeps it open on the next page.
  const choose = () => { setOpen(false); (document.activeElement as HTMLElement | null)?.blur(); };

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    const onDown = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    window.addEventListener('keydown', onKey);
    window.addEventListener('mousedown', onDown);
    return () => { window.removeEventListener('keydown', onKey); window.removeEventListener('mousedown', onDown); };
  }, [open]);

  return (
    <div
      ref={ref}
      className={`nav-dd${open ? ' open' : ''}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOpen(false); }}
    >
      <Link className="navlink" to="/product" onClick={choose} style={{ ...linkStyle, paddingRight: 2 }}>Product</Link>
      <button type="button" className="nav-dd-btn" aria-label="Product menu" aria-expanded={open} aria-controls="product-menu" onClick={() => setOpen(o => !o)}>
        <ChevronDown size={15} aria-hidden="true" />
      </button>
      <div className="nav-dd-pad">
        <ul id="product-menu" className="nav-dd-menu" aria-label="Product">
          {SUB_PRODUCTS.map(p => (
            <li key={p.slug}>
              <Link to={p.href} className="nav-dd-item" onClick={choose}>
                <span className="nav-dd-name">{p.name}</span>
                <span className="nav-dd-desc">{p.menu}</span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

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
            {NAV_LINKS.map(l => 'children' in l
              ? <ProductMenu key={l.label} />
              : l.external
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
            {NAV_LINKS.map(l => 'children' in l
              ? (
                <div key={l.label} style={{ display: 'flex', flexDirection: 'column' }}>
                  <Link className="navlink" to={l.href} onClick={() => setMobileOpen(false)} style={linkStyle}>{l.label}</Link>
                  <div style={{ display: 'flex', flexDirection: 'column', marginLeft: 14, paddingLeft: 14, borderLeft: '1px solid var(--line)' }}>
                    {l.children.map(c => (
                      <Link key={c.slug} className="navlink" to={c.href} onClick={() => setMobileOpen(false)} style={{ ...linkStyle, fontSize: 14 }}>{c.name}</Link>
                    ))}
                  </div>
                </div>
              )
              : l.external
                ? <a key={l.label} className="navlink" href={l.href} style={linkStyle}>{l.label}</a>
                : <Link key={l.label} className="navlink" to={l.href} onClick={() => setMobileOpen(false)} style={linkStyle}>{l.label}</Link>)}
          </div>
        )}
      </div>
    </header>
  );
}
