import PillarPage from '../components/PillarPage';
import Section from '../components/Section';
import AuditChainDemo from '../demos/audit/AuditChainDemo';
import PiiDemo from '../demos/pii/PiiDemo';
import { pageMeta } from '../site/meta';

export function meta() {
  return pageMeta({ title: 'Trust — OpenProxyAI', description: 'PII redaction, prompt-injection detection, row-level tenant isolation and a tamper-evident audit trail.', path: '/trust' });
}

export default function TrustRoute() {
  return (
    <PillarPage
      pillar="trust"
      sceneId="trust"
      eyebrow="Trust"
      title="Guardrails you can test, and evidence you can verify."
      lede="Sensitive data is stripped before it leaves, risky prompts are stopped, and every decision is written to a log that cannot be quietly rewritten."
    >
      <Section eyebrow="Try it" title="Type something sensitive." lede="Runs in your browser with the same patterns the gateway uses.">
        <PiiDemo />
      </Section>
      <Section eyebrow="Try it" title="Edit the history. Watch the chain break." lede="Each entry stores the SHA-256 hash of the one before it. Change any action and every later link fails verification.">
        <AuditChainDemo />
      </Section>
    </PillarPage>
  );
}
