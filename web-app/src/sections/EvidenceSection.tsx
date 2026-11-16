import Section from '../components/Section';
import { docsPage, repoFile } from '../lib/links';

interface Row {
  claim: string;
  proof: string;
  href: string;
}

const EVIDENCE: Row[] = [
  { claim: 'Policy blocks return HTTP 446 with a plain-language explanation', proof: 'Policies and guardrails', href: docsPage('/core-concepts/policies-and-guardrails') },
  { claim: 'Requests are routed by data class, with no silent fallback', proof: 'Feature inventory', href: repoFile('docs/features.md') },
  { claim: 'MCP tool definitions are pinned and drift is refused', proof: 'MCP gateway guide', href: docsPage('/guides/mcp-gateway') },
  { claim: 'An agent’s credentials never reach a tool server', proof: 'Regression test', href: repoFile('backend/tests/test_mcp_token_isolation.py') },
  { claim: 'Each organization is isolated by Postgres row-level security', proof: 'Row-level security', href: docsPage('/security/row-level-security') },
  { claim: 'The audit log is append-only', proof: 'Audit logging', href: docsPage('/security/audit-logging') },
  { claim: 'Automated WCAG 2.1 A/AA checks pass on every console screen', proof: 'Accessibility guide', href: repoFile('docs/guides/accessibility.md') },
  { claim: 'OpenProxyAI holds no SOC 2, ISO 27001 or HIPAA certification', proof: 'Trust center', href: docsPage('/security/trust-center') },
];

export default function EvidenceSection() {
  return (
    <Section id="evidence" label="§09 · evidence" title={<>What we claim, and <em>where you can check it.</em></>} aside="no logos, no invented metrics">
      <div className="opa-card tbl-scroll">
        <table className="tbl">
          <thead>
            <tr><th scope="col">Claim</th><th scope="col">Check it</th></tr>
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
        We have no customer logos to show and no overhead benchmark to publish yet, so this page shows neither. The compliance templates (HIPAA, PCI, FedRAMP-aligned) are policy configurations that help you document your controls. They are not certifications, and using them does not make a deployment compliant.
      </p>
    </Section>
  );
}
