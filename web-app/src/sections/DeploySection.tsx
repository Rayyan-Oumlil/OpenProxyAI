import { PAGE_MAX_WIDTH } from '../lib/layout';

export default function DeploySection() {
  return (
    <section id="deploy" style={{ padding: '60px 0', borderTop: '1px solid var(--line)', scrollMarginTop: 76 }}>
      <div style={{ maxWidth: PAGE_MAX_WIDTH, margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr auto', gap: 24, alignItems: 'baseline', marginBottom: 32, paddingBottom: 12, borderBottom: '1px dashed var(--line)' }} className="sec-head">
          <span style={{ color: 'var(--ink-3)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.2em' }}>§04 · deploy</span>
          <h2 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(26px,2.8vw,38px)', letterSpacing: '-0.025em', fontWeight: 500, margin: 0, color: 'var(--ink)' }}>
            Your VPC. <em style={{ fontStyle: 'normal', color: 'var(--accent)' }}>Your keys.</em> Your data boundary.
          </h2>
          <span style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.2em' }}>self-hosted targets</span>
        </div>

        <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
          {['docker', 'helm', 'terraform', 'air-gapped'].map(tgt => (
            <span key={tgt} style={{
              fontSize: 11, color: 'var(--accent)', border: '1px solid var(--line-2)', borderRadius: 5,
              padding: '4px 10px', textTransform: 'uppercase', letterSpacing: '0.1em',
            }}>{tgt}</span>
          ))}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1.15fr 1fr', gap: 10 }} className="deploy-grid">
          {/* Install shell */}
          <div style={{ background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 10, overflow: 'hidden' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr auto', gap: 10, alignItems: 'center', padding: '10px 14px', borderBottom: '1px solid var(--line)', fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.14em' }}>
              <span style={{ display: 'flex', gap: 6 }}>
                {[0,1,2].map(i => <span key={i} style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--line-2)', display: 'inline-block' }} />)}
              </span>
              <span>~/openproxy · install.sh</span>
              <span>zsh</span>
            </div>
            <pre style={{ padding: 18, fontSize: 12.5, lineHeight: 1.7, color: 'var(--ink)', overflow: 'auto' }}>
              <span style={{ color: 'var(--ink-3)' }}>$ </span>curl -sSL openproxy.ai/install.sh <span style={{ color: 'var(--accent)' }}>|</span> sh{'\n'}
              <span style={{ color: 'var(--ink-3)' }}>$ </span>cd openproxy {'&&'} docker compose up -d{'\n'}
              {'  '}<span style={{ color: 'var(--accent)' }}>✔</span> postgres        <span style={{ color: 'var(--ink-3)' }}>(pgvector enabled)</span>{'\n'}
              {'  '}<span style={{ color: 'var(--accent)' }}>✔</span> redis{'\n'}
              {'  '}<span style={{ color: 'var(--accent)' }}>✔</span> backend         <span style={{ color: 'var(--ink-3)' }}>(fastapi · async)</span>{'\n'}
              {'  '}<span style={{ color: 'var(--accent)' }}>✔</span> admin-console{'\n'}
              {'\n'}
              <span style={{ color: 'var(--ink-3)' }}>$ </span>docker compose exec backend alembic upgrade head{'\n'}
              {'  '}<span style={{ color: 'var(--accent)' }}>✔</span> migrations applied · up to date{'\n'}
              {'\n'}
              <span style={{ color: 'var(--ink-3)' }}># → admin console ready ✓</span>
            </pre>
          </div>

          {/* Python example */}
          <div style={{ background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 10, overflow: 'hidden' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr auto', gap: 10, alignItems: 'center', padding: '10px 14px', borderBottom: '1px solid var(--line)', fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.14em' }}>
              <span style={{ display: 'flex', gap: 6 }}>
                {[0,1,2].map(i => <span key={i} style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--line-2)', display: 'inline-block' }} />)}
              </span>
              <span>chat.py · first call</span>
              <span>python</span>
            </div>
            <pre style={{ padding: 18, fontSize: 12.5, lineHeight: 1.7, color: 'var(--ink)', overflow: 'auto' }}>
              <span style={{ color: '#c7a2ff' }}>from</span> openai <span style={{ color: '#c7a2ff' }}>import</span> OpenAI{'\n'}
              {'\n'}
              client = OpenAI({'\n'}
              {'  '}base_url=<span style={{ color: '#8bc6ff' }}>"https://api.openproxy.ai/v1"</span>,{'\n'}
              {'  '}api_key=os.environ[<span style={{ color: '#8bc6ff' }}>"OPENPROXY_KEY"</span>],{'\n'}
              ){'\n'}
              {'\n'}
              <span style={{ color: 'var(--ink-3)' }}># same SDK · every provider · every policy</span>{'\n'}
              r = client.chat.completions.create({'\n'}
              {'  '}model=<span style={{ color: '#8bc6ff' }}>"gpt-4o"</span>,{'\n'}
              {'  '}messages=[{'{'}<span style={{ color: '#8bc6ff' }}>"role"</span>:<span style={{ color: '#8bc6ff' }}>"user"</span>,<span style={{ color: '#8bc6ff' }}>"content"</span>:<span style={{ color: '#8bc6ff' }}>"hi"</span>{'}'}],{'\n'}
              {'  '}extra_headers={'{'}{'\n'}
              {'    '}<span style={{ color: '#8bc6ff' }}>"x-op-team"</span>:   <span style={{ color: '#8bc6ff' }}>"eng-platform"</span>,{'\n'}
              {'    '}<span style={{ color: '#8bc6ff' }}>"x-op-policy"</span>: <span style={{ color: '#8bc6ff' }}>"pii_redact,topic_guard"</span>,{'\n'}
              {'  '}{'}'},{'\n'}
              ){'\n'}
              {'\n'}
              <span style={{ color: 'var(--accent)' }}># → request logged · cost $0.0124 · cache miss</span>
            </pre>
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 1000px) {
          .deploy-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </section>
  );
}
