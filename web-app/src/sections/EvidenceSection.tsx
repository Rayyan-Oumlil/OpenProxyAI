import Section from '../components/Section';
import { docsPage, repoFile } from '../lib/links';

interface Row {
  claim: string;
  proof: string;
  href: string;
}

const EVIDENCE: Row[] = [
  { claim: 'Requests with sensitive data can be blocked, with a plain explanation for the user', proof: 'Policy documentation', href: docsPage('/core-concepts/policies-and-guardrails') },
  { claim: 'Data is routed by sensitivity and never silently sent to another model', proof: 'Feature list', href: repoFile('docs/features.md') },
  { claim: 'AI agent tools are locked once approved, and changes are blocked until reviewed', proof: 'Agent tools guide', href: docsPage('/guides/mcp-gateway') },
  { claim: 'Your people’s credentials are never passed on to a tool', proof: 'Automated test', href: repoFile('backend/tests/test_mcp_token_isolation.py') },
  { claim: 'Each organization’s data is kept separate at the database level', proof: 'Isolation documentation', href: docsPage('/security/row-level-security') },
  { claim: 'The activity record is append-only: entries are never edited or deleted', proof: 'Audit documentation', href: docsPage('/security/audit-logging') },
  { claim: 'Automated accessibility checks (WCAG 2.1 A/AA) pass on every admin screen', proof: 'Accessibility guide', href: repoFile('docs/guides/accessibility.md') },
  { claim: 'OpenProxyAI holds no SOC 2, ISO 27001 or HIPAA certification', proof: 'Trust center', href: docsPage('/security/trust-center') },
];

export default function EvidenceSection() {
  return (
    <Section id="evidence" label="Evidence" title={<>What we claim, and <em>where you can check it.</em></>} aside="no invented numbers">
      <div className="tbl-scroll">
        <table className="tbl">
          <thead>
            <tr><th scope="col">Claim</th><th scope="col">Proof</th></tr>
          </thead>
          <tbody>
            {EVIDENCE.map(row => (
              <tr key={row.claim}>
                <td>{row.claim}</td>
                <td><a href={row.href} target="_blank" rel="noopener noreferrer">{row.proof} →</a></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="note">
        We have no customer logos to show and no speed benchmark to publish yet, so this page shows neither. The compliance templates are configurations that help you document your controls. They are not certifications, and using them does not make a deployment compliant.
      </p>
    </Section>
  );
}
