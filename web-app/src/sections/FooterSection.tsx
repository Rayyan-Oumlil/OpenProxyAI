import { Link } from 'react-router-dom';
import { DOCS_URL, GITHUB_URL } from '../lib/links';
import Logo from '../components/Logo';

export default function FooterSection() {
  const year = new Date().getFullYear();
  const linkStyle = { color: 'inherit', textDecoration: 'none' } as const;
  return (
    <footer style={{ padding: '30px 0', borderTop: '1px solid var(--line)', fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.15em' }}>
      <div className="sec-wrap" style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 14, textTransform: 'none', letterSpacing: 0 }}><Logo /><span style={{ textTransform: 'uppercase', letterSpacing: '0.15em' }}>© {year} · Apache-2.0</span></span>
        <nav aria-label="Footer" style={{ display: 'flex', gap: 18, flexWrap: 'wrap' }}>
          <a href={GITHUB_URL} style={linkStyle} target="_blank" rel="noopener noreferrer">GitHub</a>
          <a href={DOCS_URL} style={linkStyle} target="_blank" rel="noopener noreferrer">Docs</a>
          <Link to="/security" style={linkStyle}>Security</Link>
          <Link to="/compare" style={linkStyle}>Compare</Link>
          <Link to="/pricing" style={linkStyle}>Pricing</Link>
        </nav>
        <span>Policy templates: HIPAA · PCI · FedRAMP-aligned (templates, not certifications)</span>
      </div>
    </footer>
  );
}
