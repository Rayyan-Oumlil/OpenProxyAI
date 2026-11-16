import Section from '../components/Section';
import { docsPage, repoFile } from '../lib/links';

interface Control {
  control: string;
  how: string;
  proof: string;
  href: string;
}

const CONTROLS: Control[] = [
  { control: 'Tenant isolation', how: 'Postgres row-level security scopes every query to one organization, enforced in the database as well as in application code.', proof: 'Row-level security', href: docsPage('/security/row-level-security') },
  { control: 'Audit trail', how: 'Every request, policy decision and routing outcome is recorded. Rows are append-only. By default the log keeps metadata, not what users typed.', proof: 'Audit logging', href: docsPage('/security/audit-logging') },
  { control: 'Data-class routing', how: 'Each request gets a class. A registry decides which models and keys may serve it. No silent fallback.', proof: 'Feature inventory', href: repoFile('docs/features.md') },
  { control: 'Outbound connections', how: 'Custom provider endpoints are validated when saved and guarded on every connection, against internal addresses and redirects.', proof: 'Feature inventory', href: repoFile('docs/features.md') },
  { control: 'MCP tools', how: 'Tool definitions are pinned by hash, results can taint a session, and an agent’s credentials are never forwarded to a tool server.', proof: 'MCP gateway guide', href: docsPage('/guides/mcp-gateway') },
  { control: 'Identity', how: 'Role-based access, OpenID Connect sign-in and SCIM 2.0 provisioning (Okta, Entra ID). SAML is not supported.', proof: 'SSO and SCIM', href: docsPage('/guides/sso-and-scim') },
  { control: 'Data residency', how: 'One region per organization. Requests only use provider keys and models tagged for that region, including on failover. The tags are your statements; the gateway cannot verify them with the provider.', proof: 'Data residency', href: docsPage('/security/data-residency') },
  { control: 'Secrets', how: 'Provider keys come from environment variables, HashiCorp Vault or AWS Secrets Manager, and are never logged in plaintext.', proof: 'Secrets from Vault', href: docsPage('/guides/secrets-from-vault') },
];

export default function ControlsSection() {
  return (
    <Section id="controls" label="§01 · controls" title={<>What each control does, <em>and where to verify it.</em></>} aside="read the docs, read the code">
      <div className="opa-card tbl-scroll">
        <table className="tbl">
          <thead>
            <tr><th scope="col">Control</th><th scope="col">How it works</th><th scope="col">Check it</th></tr>
          </thead>
          <tbody>
            {CONTROLS.map(c => (
              <tr key={c.control}>
                <td style={{ whiteSpace: 'nowrap' }}>{c.control}</td>
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
