import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import PageCta from '../components/PageCta';
import Section from '../components/Section';
import { KeyValue, Shot } from '../components/blocks';
import ControlsSection from '../sections/ControlsSection';
import LimitsSection from '../sections/LimitsSection';
import ComplianceSection from '../sections/ComplianceSection';
import AuditTrailSection from '../sections/AuditTrailSection';
import AccessControlSection from '../sections/AccessControlSection';
import RegulationSection from '../sections/RegulationSection';
import VerifySection from '../sections/VerifySection';

const QUESTIONS = [
  { q: 'Where does OpenProxyAI run?', a: 'In your own environment. You install and operate it alongside your existing systems.' },
  { q: 'Do our requests pass through your company?', a: 'No. Requests go from your environment to the AI models you approved. There is no hosted service.' },
  { q: 'What is stored in a record?', a: 'By default the record keeps metadata: who asked, which model, the cost and the decision. It does not keep what people typed. Keeping redacted samples of prompts and answers is an option you turn on yourself.' },
  { q: 'Do you hold security certifications?', a: 'No. OpenProxyAI holds no SOC 2, ISO 27001 or HIPAA certification, and the compliance templates are starting points, not certifications.' },
];

export default function SecurityPage() {
  useEffect(() => { document.title = 'Security and compliance | OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Security"
        title={<>Built to be checked, <span style={{ color: 'var(--soft)' }}>not taken on trust.</span></>}
        description="This page is for the people who review OpenProxyAI before it is approved. Each control is paired with the place where you can confirm it yourself. We say what is and is not certified, and we link every claim to a document, a test or the code."
        secondary={{ label: 'Go to the controls', href: '#controls' }}
        visual={
          <KeyValue
            rows={[
              { k: 'Where it runs', v: 'Inside your own environment, under your own security controls.' },
              { k: 'What leaves your environment', v: 'Only the requests your rules allow, to the AI models you approved.' },
              { k: 'What is recorded', v: 'Every decision, with the rule that applied and what the person was told.' },
              { k: 'Independent certifications', v: 'None. No SOC 2, ISO 27001 or HIPAA certification.' },
            ]}
          />
        }
      />
      <ControlsSection />
      <Section id="record" label="The evidence" title="What a single stopped request leaves behind." aside="A real request record from the console, with sample data, and the same fields in plain words.">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 32, alignItems: 'center' }}>
          <div style={{ flex: '1.2 1 420px', minWidth: 0 }}>
            <Shot src="/images/console/trace.webp" alt="OpenProxyAI request record: a request blocked because personal data was detected, what the caller was told, and the request ID." />
          </div>
          <div style={{ flex: '1 1 360px', minWidth: 0 }}>
            <KeyValue
              rows={[
                { k: 'Decision', v: 'Stopped', tone: 'stop' },
                { k: 'What was found', v: 'Confidential: a Social Security number' },
                { k: 'The caller was told', v: 'This request appears to contain personal or sensitive data that your organization’s policy does not allow to be sent.' },
                { k: 'Reached the AI model', v: 'No' },
                { k: 'Identifier', v: 'A unique request ID on every record' },
              ]}
            />
          </div>
        </div>
      </Section>
      <LimitsSection />
      <ComplianceSection />
      <AuditTrailSection />
      <AccessControlSection />
      <RegulationSection />
      <VerifySection />
      <Section id="questions" label="Questions reviewers ask" title="Plain answers.">
        <div>
          {QUESTIONS.map(x => (
            <div key={x.q} style={{ borderTop: '1px solid var(--line)', padding: '24px 0', display: 'flex', flexWrap: 'wrap', gap: '8px 48px' }}>
              <h3 style={{ flex: '1 1 300px', margin: 0, fontSize: 20, fontWeight: 500, letterSpacing: '-0.015em' }}>{x.q}</h3>
              <p style={{ flex: '1.6 1 360px', margin: 0, fontSize: 16, color: 'var(--ink-2)', textWrap: 'pretty' }}>{x.a}</p>
            </div>
          ))}
        </div>
      </Section>
      <PageCta title="Bring your reviewers. We will walk through every control." body="A working session with your security and compliance team, on the product itself." />
    </>
  );
}
