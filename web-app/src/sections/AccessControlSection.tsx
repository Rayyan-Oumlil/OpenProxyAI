import Section from '../components/Section';

const CONTROLS = [
  { layer: 'Identity', title: 'Single sign-on and automatic provisioning', desc: 'People sign in through your identity provider, and accounts are created, updated and removed automatically (Okta, Microsoft Entra ID). Included on the Enterprise plan. SAML is not supported.' },
  { layer: 'Keys and budgets', title: 'Team-scoped access keys', desc: 'Access keys and budgets belong to a team. A key can only spend that team’s budget and use the models that team is allowed to use.' },
  { layer: 'Membership', title: 'Roles and invitations', desc: 'People join by invitation and hold a role. Access is removed by removing the person, not by changing a password everyone shared.' },
  { layer: 'Data', title: 'Separation by organization', desc: 'Each organization’s records are kept apart at the database level, so one business unit cannot see another’s.' },
];

export default function AccessControlSection() {
  return (
    <Section id="access" label="Access control" title={<>Who can do what, <em>enforced at every layer.</em></>} aside="identity, keys, data">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 900 }}>
        {CONTROLS.map(c => (
          <div key={c.title} className="layer-row opa-card" style={{ display: 'grid', gridTemplateColumns: '150px minmax(0,1fr)', gap: 20, padding: '18px 22px', alignItems: 'center' }}>
            <span style={{ color: 'var(--ink)', fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{c.layer}</span>
            <div>
              <div style={{ color: 'var(--ink)', fontSize: 15.5, fontWeight: 600, marginBottom: 4 }}>{c.title}</div>
              <div style={{ color: 'var(--ink-2)', fontFamily: 'var(--sans)', fontSize: 14.5, lineHeight: 1.6 }}>{c.desc}</div>
            </div>
          </div>
        ))}
      </div>
      <style>{`@media (max-width: 1000px) { .layer-row { grid-template-columns: minmax(0,1fr) !important; gap: 6px !important; } }`}</style>
    </Section>
  );
}
