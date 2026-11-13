import { PAGE_MAX_WIDTH } from '../lib/layout';

export default function FooterSection() {
  const today = new Date().getFullYear();
  return (
    <footer style={{ padding: '30px 0', borderTop: '1px solid var(--line)', fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.15em' }}>
      <div style={{ maxWidth: PAGE_MAX_WIDTH, margin: '0 auto', padding: '0 24px', display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <span>© {today} OpenProxyAI</span>
        <span>Policy templates: HIPAA · PCI · FedRAMP (templates, not certifications)</span>
      </div>
    </footer>
  );
}
