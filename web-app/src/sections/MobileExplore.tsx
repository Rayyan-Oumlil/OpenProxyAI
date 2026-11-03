import { Link } from 'react-router-dom';
import { PAGE_MAX_WIDTH } from '../lib/layout';

const LINKS = [
  { to: '/product', title: 'Product', text: 'The request pipeline, caching and observability.' },
  { to: '/security', title: 'Security', text: 'Tenant isolation, audit trail and compliance evidence.' },
  { to: '/providers', title: 'Providers', text: 'Every model behind one key, with failover.' },
  { to: '/pricing', title: 'Pricing', text: 'Community free. Team and Business plans.' },
];

/** Phones only: points at the detail pages that the longer desktop home page inlines. */
export default function MobileExplore() {
  return (
    <section className="lg:hidden" aria-labelledby="explore-title" style={{ borderTop: '1px solid var(--line)', padding: '48px 24px' }}>
      <div style={{ maxWidth: PAGE_MAX_WIDTH, margin: '0 auto' }}>
        <h2 id="explore-title" style={{ fontSize: 20, margin: '0 0 20px', color: 'var(--ink)' }}>Explore</h2>
        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 12 }}>
          {LINKS.map((link) => (
            <li key={link.to}>
              <Link to={link.to} style={{ display: 'block', padding: 16, border: '1px solid var(--line)', borderRadius: 8, textDecoration: 'none', color: 'var(--ink)' }}>
                <strong style={{ display: 'block', marginBottom: 4 }}>{link.title} →</strong>
                <span style={{ color: 'var(--ink-2)', fontSize: 14 }}>{link.text}</span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
