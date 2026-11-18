import { Link } from 'react-router-dom';
import { DOCS_URL, GITHUB_URL } from '../lib/links';
import Logo from '../components/Logo';

export default function FooterSection() {
  const year = new Date().getFullYear();
  return (
    <footer style={{ borderTop: '1px solid var(--line)', background: 'var(--bg-2)', padding: '40px 24px' }}>
      <div style={{ maxWidth: 1240, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '20px 40px', alignItems: 'center', justifyContent: 'space-between' }}>
          <Logo />
          <nav aria-label="Footer" style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 28px' }}>
            {[['Product', '/product'], ['Security', '/security'], ['Integrations', '/providers'], ['Compare', '/compare'], ['Pricing', '/pricing']].map(([l, h]) => (
              <Link key={l} className="navlink" to={h} style={{ fontSize: 15, minHeight: 44, display: 'flex', alignItems: 'center' }}>{l}</Link>
            ))}
            <a className="navlink" href={DOCS_URL} target="_blank" rel="noopener noreferrer" style={{ fontSize: 15, minHeight: 44, display: 'flex', alignItems: 'center' }}>Docs</a>
            <a className="navlink" href={GITHUB_URL} target="_blank" rel="noopener noreferrer" style={{ fontSize: 15, minHeight: 44, display: 'flex', alignItems: 'center' }}>GitHub</a>
          </nav>
          <span style={{ fontSize: 14, color: 'var(--ink-3)' }}>© {year} OpenProxyAI · Apache-2.0</span>
        </div>
        <p style={{ margin: 0, fontSize: 13, color: 'var(--ink-3)' }}>Policy templates: HIPAA · PCI · FedRAMP-aligned. These are templates, not certifications.</p>
      </div>
    </footer>
  );
}
