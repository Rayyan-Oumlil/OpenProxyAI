export default function FooterSection() {
  const today = new Date().getFullYear();
  return (
    <footer style={{ padding: '30px 0', borderTop: '1px solid var(--line)', fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.15em' }}>
      <div style={{ maxWidth: 1380, margin: '0 auto', padding: '0 24px', display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <span>© {today} OpenProxyAI · build 2.4.1</span>
        <span>SOC 2 · HIPAA · PCI-DSS · FedRAMP · Status: all systems operational</span>
        <span>api.openproxy.ai · /health 200</span>
      </div>
    </footer>
  );
}
