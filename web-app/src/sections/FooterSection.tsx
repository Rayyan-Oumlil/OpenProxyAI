import { Link } from 'react-router-dom';
import { DOCS_URL, GITHUB_URL } from '../lib/links';

export default function FooterSection() {
  const year = new Date().getFullYear();
  const linkStyle = { color: 'inherit', textDecoration: 'none' } as const;
  return (
    <footer style={{ padding: '30px 0', borderTop: '1px solid var(--line)', fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.15em' }}>
      <div className="sec-wrap" style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <span>© {year} OpenProxyAI · Apache-2.0</span>
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
