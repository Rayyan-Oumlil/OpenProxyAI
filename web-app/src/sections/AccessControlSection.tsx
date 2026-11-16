import Section from '../components/Section';

const CONTROLS = [
  { layer: 'identity', title: 'OIDC sign-in and SCIM 2.0', desc: 'Members sign in through your identity provider over OpenID Connect, and SCIM creates, updates and deactivates users automatically (Okta, Entra ID). SSO and SCIM are included on the Enterprise plan. SAML is not supported.' },
  { layer: 'key & budget', title: 'Team-scoped keys', desc: 'API keys and budgets are scoped to a team. A key can only spend against its team’s budget and call the models that team is allowed to use.' },
  { layer: 'membership', title: 'Roles and invites', desc: 'Members join by invite and hold a role. Access is removed by removing the member, not by rotating a credential everyone shared.' },
  { layer: 'data', title: 'Row-level isolation', desc: 'Postgres row-level security scopes each query to one organization, so a bug in application code cannot return another organization’s rows.' },
];

export default function AccessControlSection() {
  return (
    <Section id="access" label="§05 · access control" title={<>Who can do what, <em>enforced at every layer.</em></>} aside="identity · keys · data">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 860 }}>
        {CONTROLS.map(c => (
          <div key={c.title} className="layer-row" style={{ display: 'grid', gridTemplateColumns: '110px minmax(0,1fr)', gap: 20, padding: '16px 20px', border: '1px solid var(--line)', borderRadius: 8, background: 'var(--panel)', alignItems: 'center' }}>
            <span style={{ color: 'var(--accent)', fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.12em' }}>{c.layer}</span>
            <div>
              <div style={{ color: 'var(--ink)', fontSize: 13.5, fontWeight: 500, marginBottom: 4 }}>{c.title}</div>
              <div style={{ color: 'var(--ink-2)', fontFamily: 'var(--sans)', fontSize: 14, lineHeight: 1.6 }}>{c.desc}</div>
            </div>
          </div>
        ))}
      </div>
      <style>{`@media (max-width: 1000px) { .layer-row { grid-template-columns: minmax(0,1fr) !important; gap: 6px !important; } }`}</style>
    </Section>
  );
}
