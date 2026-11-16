import Section from '../components/Section';
import CodeBlock from '../components/CodeBlock';

export default function AuditTrailSection() {
  return (
    <Section id="audit" label="§04 · audit trail" title={<>Append-only. <em>Open any request</em> and see why.</>} aside="example entry">
      <div className="split">
        <CodeBlock title="audit log · example entry" tag="illustrative values">
          <span className="tok-dim">request_id</span>{'  req_01J3K9A2XM\n'}
          <span className="tok-dim">team</span>{'        eng-platform\n'}
          <span className="tok-dim">model</span>{'       gpt-4o\n'}
          <span className="tok-dim">data_class</span>{'  internal\n'}
          <span className="tok-dim">policy</span>{'      enforce · pass\n'}
          <span className="tok-dim">cache</span>{'       miss\n'}
          <span className="tok-dim">logged_at</span>{'   2026-11-16T03:35:41Z\n'}
          <span className="tok-ok">trace</span>{'       open the request trace'}
        </CodeBlock>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <p className="lede">
            Every request is recorded: not sampled, not aggregated after the fact. By default the log keeps metadata (model, tokens, cost, status, data class and the policy decision), not what users typed. Keeping redacted samples of prompts and answers is an opt-in you turn on yourself.
          </p>
          <p className="lede">
            Open a request by its ID to see which check fired, which cache tier answered, which route was chosen and what it cost. Entries are archived once they pass the retention window of your plan, and you can export security events to your SIEM.
          </p>
        </div>
      </div>
    </Section>
  );
}
