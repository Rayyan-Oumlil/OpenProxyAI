import { Link } from 'react-router-dom';
import { GITHUB_URL, repoFile } from '../lib/links';

interface TrustItem {
  label: string;
  detail: string;
  href: string;
  external: boolean;
}

const ITEMS: TrustItem[] = [
  { label: 'Apache-2.0', detail: 'read the licence', href: repoFile('LICENSE'), external: true },
  { label: 'Self-hosted', detail: 'your VPC, your keys', href: '#deploy', external: false },
  { label: 'Air-gap mode', detail: 'no calls home', href: '#deploy', external: false },
  { label: 'Automated WCAG 2.1 A/AA checks', detail: 'on every console screen', href: repoFile('docs/guides/accessibility.md'), external: true },
  { label: 'Every claim has a source', detail: 'see the evidence table', href: '#evidence', external: false },
];

export default function TrustStrip() {
  return (
    <section aria-label="Trust" style={{ borderTop: '1px solid var(--line)', borderBottom: '1px solid var(--line)', background: 'var(--bg-2)' }}>
      <ul className="sec-wrap" style={{ listStyle: 'none', margin: '0 auto', padding: '14px 24px', display: 'flex', flexWrap: 'wrap', gap: '10px 28px', fontSize: 12 }}>
        {ITEMS.map(item => (
          <li key={item.label}>
            {item.external ? (
              <a href={item.href} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--ink)', textDecoration: 'none' }}>
                <span style={{ color: 'var(--accent)' }}>✓ </span>{item.label} <span style={{ color: 'var(--ink-3)' }}>· {item.detail}</span>
              </a>
            ) : (
              <a href={item.href} style={{ color: 'var(--ink)', textDecoration: 'none' }}>
                <span style={{ color: 'var(--accent)' }}>✓ </span>{item.label} <span style={{ color: 'var(--ink-3)' }}>· {item.detail}</span>
              </a>
            )}
          </li>
        ))}
        <li style={{ marginLeft: 'auto' }}>
          <Link to="/security" style={{ color: 'var(--ink-2)', textDecoration: 'none' }}>security →</Link>{' '}
          <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--ink-2)', textDecoration: 'none', marginLeft: 12 }}>source →</a>
        </li>
      </ul>
    </section>
  );
}
