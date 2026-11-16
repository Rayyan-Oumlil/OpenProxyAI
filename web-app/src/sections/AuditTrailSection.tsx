import Section from '../components/Section';
import ChecklistCard from '../components/ChecklistCard';

export default function AuditTrailSection() {
  return (
    <Section id="audit" label="Audit trail" title={<>Open any request <em>and see why.</em></>} aside="permanent, append-only">
      <div className="split">
        <ChecklistCard
          title="What each record shows"
          items={[
            { text: 'Who asked: the person, team and application', ok: true },
            { text: 'Which model, and what it cost', ok: true },
            { text: 'The sensitivity of the data', ok: true },
            { text: 'The decision, and the rule behind it', ok: true },
            { text: 'Whether a saved answer was reused', ok: true },
            { text: 'When it happened', ok: true },
          ]}
        />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <p className="lede">
            Every request is recorded: not sampled, not summarized afterwards. By default the record keeps metadata, not what people typed. Keeping redacted samples of prompts and answers is an option you turn on yourself.
          </p>
          <p className="lede">
            Records are archived once they pass the retention period of your plan, and security events can be exported to your monitoring tools.
          </p>
        </div>
      </div>
    </Section>
  );
}
