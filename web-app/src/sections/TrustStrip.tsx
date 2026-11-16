import { repoFile } from '../lib/links';

interface TrustItem {
  label: string;
  detail: string;
  href: string;
  external: boolean;
}

const ITEMS: TrustItem[] = [
  { label: 'Open source', detail: 'Apache-2.0 licence', href: repoFile('LICENSE'), external: true },
  { label: 'Runs in your environment', detail: 'cloud, data center or air-gapped', href: '#deploy', external: false },
  { label: 'No vendor in the middle', detail: 'you operate it yourself', href: '#deploy', external: false },
  { label: 'Accessibility tested', detail: 'automated WCAG 2.1 A/AA checks', href: repoFile('docs/guides/accessibility.md'), external: true },
  { label: 'Every claim sourced', detail: 'see the evidence table', href: '#evidence', external: false },
];

export default function TrustStrip() {
  return (
    <section aria-label="Trust" style={{ borderTop: '1px solid var(--line)', borderBottom: '1px solid var(--line)', background: 'var(--bg-2)' }}>
      <ul className="sec-wrap" style={{ listStyle: 'none', margin: '0 auto', padding: '16px 24px', display: 'flex', flexWrap: 'wrap', gap: '10px 32px', fontSize: 13.5 }}>
        {ITEMS.map(item => (
          <li key={item.label}>
            <a
              href={item.href}
              {...(item.external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
              style={{ color: 'var(--ink)', textDecoration: 'none' }}
            >
              <span style={{ color: 'var(--accent)', fontWeight: 700 }}>✓ </span>
              <strong style={{ fontWeight: 600 }}>{item.label}</strong> <span style={{ color: 'var(--ink-3)' }}>· {item.detail}</span>
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
