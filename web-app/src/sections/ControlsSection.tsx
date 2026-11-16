import Section from '../components/Section';
import { docsPage, repoFile } from '../lib/links';

interface Control {
  control: string;
  how: string;
  proof: string;
  href: string;
}

const CONTROLS: Control[] = [
  { control: 'Separation of organizations', how: 'Each organization’s data is kept apart at the database level, so a mistake in the application cannot show one organization another’s records.', proof: 'Isolation documentation', href: docsPage('/security/row-level-security') },
  { control: 'Permanent record', how: 'Every request, decision and outcome is recorded and cannot be edited. By default the record keeps who, what model, cost and decision, not what people typed.', proof: 'Audit documentation', href: docsPage('/security/audit-logging') },
  { control: 'Data protection by sensitivity', how: 'Each request gets a sensitivity level, and you approve which models may handle each level. Nothing is silently rerouted.', proof: 'Feature list', href: repoFile('docs/features.md') },
  { control: 'Safe connections', how: 'Connections to private or custom AI endpoints are checked when saved and on every use, so they cannot be pointed at internal systems by mistake.', proof: 'Feature list', href: repoFile('docs/features.md') },
  { control: 'AI agent tools', how: 'Tools are approved by you, locked once approved, and screened. People’s credentials are never passed to a tool.', proof: 'Agent tools guide', href: docsPage('/guides/mcp-gateway') },
  { control: 'Identity', how: 'Roles, single sign-on and automatic user provisioning with Okta or Microsoft Entra ID. SAML is not supported.', proof: 'Sign-on guide', href: docsPage('/guides/sso-and-scim') },
  { control: 'Data location', how: 'Each organization has one region. Requests only use accounts and models tagged for that region, including when failing over. The tags are your statements: the gateway cannot verify them with the provider.', proof: 'Data location guide', href: docsPage('/security/data-residency') },
  { control: 'Secrets', how: 'Provider keys come from your own secrets manager (HashiCorp Vault or AWS Secrets Manager) and are never written to logs in plain text.', proof: 'Secrets guide', href: docsPage('/guides/secrets-from-vault') },
  { control: 'Administration', how: 'Limits on sign-in attempts, restricted access to technical metrics, and only owners or administrators can revoke access keys.', proof: 'Feature list', href: repoFile('docs/features.md') },
];

export default function ControlsSection() {
  return (
    <Section id="controls" label="Controls" title={<>What each control does, <em>and where to verify it.</em></>} aside="read the docs, read the code">
      <div className="opa-card tbl-scroll">
        <table className="tbl">
          <thead>
            <tr><th scope="col">Control</th><th scope="col">What it does</th><th scope="col">Proof</th></tr>
          </thead>
          <tbody>
            {CONTROLS.map(c => (
              <tr key={c.control}>
                <td style={{ whiteSpace: 'nowrap', fontWeight: 600 }}>{c.control}</td>
                <td>{c.how}</td>
                <td style={{ whiteSpace: 'nowrap' }}><a href={c.href} target="_blank" rel="noopener noreferrer">{c.proof} →</a></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  );
}
