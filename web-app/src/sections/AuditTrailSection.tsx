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
            <div className="opa-card-head"><span>audit_log · example entry</span><span>append-only</span></div>
            <pre style={{ padding: 18, fontSize: 12.5, lineHeight: 1.7, color: 'var(--ink)', overflow: 'auto' }}>
              <span style={{ color: 'var(--ink-3)' }}>request_id</span>{'  req_01J3K9A2XM\n'}
              <span style={{ color: 'var(--ink-3)' }}>org</span>{'         acme-corp\n'}
              <span style={{ color: 'var(--ink-3)' }}>team</span>{'        eng-platform\n'}
              <span style={{ color: 'var(--ink-3)' }}>user</span>{'        m.patel@acme.com\n'}
              <span style={{ color: 'var(--ink-3)' }}>model</span>{'       gpt-4o\n'}
              <span style={{ color: 'var(--ink-3)' }}>policy</span>{'      enforce · pass\n'}
              <span style={{ color: 'var(--ink-3)' }}>cost_usd</span>{'    0.0124\n'}
              <span style={{ color: 'var(--ink-3)' }}>logged_at</span>{'   2026-08-08T03:35:41Z\n'}
              <span style={{ color: 'var(--accent)' }}>replay</span>{'      open the trace'}
            </pre>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, justifyContent: 'center' }}>
            <p style={{ color: 'var(--ink-2)', fontSize: 14, lineHeight: 1.7, margin: 0 }}>
              Every field above is recorded for every request: not sampled, not aggregated after the fact. By default the log keeps metadata (model, tokens, cost, status and the policy decision), not what users typed. Keeping redacted samples of prompts and answers is an opt-in you turn on yourself.
            </p>
            <p style={{ color: 'var(--ink-2)', fontSize: 14, lineHeight: 1.7, margin: 0 }}>
              Open a request by its ID to see the pipeline decision: which check fired, which cache tier answered, which route was chosen, what it cost. Entries are append-only, and logs are archived once they pass the retention window of your plan.
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
