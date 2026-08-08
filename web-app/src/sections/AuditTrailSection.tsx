import { PAGE_MAX_WIDTH } from '../lib/layout';

export default function AuditTrailSection() {
  return (
    <section style={{ padding: '60px 0', borderTop: '1px solid var(--line)' }}>
      <div style={{ maxWidth: PAGE_MAX_WIDTH, margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr auto', gap: 24, alignItems: 'baseline', marginBottom: 32, paddingBottom: 12, borderBottom: '1px dashed var(--line)' }} className="sec-head">
          <span style={{ color: 'var(--ink-3)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.2em' }}>§02 · audit trail</span>
          <h2 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(26px,2.8vw,38px)', letterSpacing: '-0.025em', fontWeight: 500, margin: 0, color: 'var(--ink)' }}>
            Write-once. <em style={{ fontStyle: 'normal', color: 'var(--accent)' }}>Never edited,</em> never deleted.
          </h2>
          <span style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.2em' }}>sample entry</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }} className="audit-grid">
          <div className="opa-card">
            <div className="opa-card-head"><span>audit_log · entry #48213</span><span>immutable</span></div>
            <pre style={{ padding: 18, fontSize: 12.5, lineHeight: 1.7, color: 'var(--ink)', overflow: 'auto' }}>
              <span style={{ color: 'var(--ink-3)' }}>request_id</span>{'  req_01J3K9A2XM\n'}
              <span style={{ color: 'var(--ink-3)' }}>org</span>{'         acme-corp\n'}
              <span style={{ color: 'var(--ink-3)' }}>team</span>{'        eng-platform\n'}
              <span style={{ color: 'var(--ink-3)' }}>user</span>{'        m.patel@acme.com\n'}
              <span style={{ color: 'var(--ink-3)' }}>model</span>{'       gpt-4o\n'}
              <span style={{ color: 'var(--ink-3)' }}>policy</span>{'      pii_redact: 1 span redacted\n'}
              <span style={{ color: 'var(--ink-3)' }}>cost_usd</span>{'    0.0124\n'}
              <span style={{ color: 'var(--ink-3)' }}>logged_at</span>{'   2026-08-08T03:35:41Z\n'}
              <span style={{ color: 'var(--accent)' }}>replay</span>{'      available'}
            </pre>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, justifyContent: 'center' }}>
            <p style={{ color: 'var(--ink-2)', fontSize: 14, lineHeight: 1.7, margin: 0 }}>
              Every field above is captured for every request — not sampled, not aggregated after the fact. The full original request and the redacted version sent upstream are both stored, so an auditor can see exactly what left your network and exactly what a policy changed before it did.
            </p>
            <p style={{ color: 'var(--ink-2)', fontSize: 14, lineHeight: 1.7, margin: 0 }}>
              Entries are replay-able: given a request ID, you can reconstruct the full pipeline decision — which policy fired, which cache tier was checked, which provider key served it — months later, without relying on anyone's memory of what happened.
            </p>
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 1000px) {
          .sec-head { grid-template-columns: 1fr !important; }
          .audit-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </section>
  );
}
