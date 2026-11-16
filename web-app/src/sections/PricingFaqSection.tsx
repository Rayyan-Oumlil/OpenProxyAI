import Section from '../components/Section';

const FAQS = [
  { q: 'Do you charge per token?', a: 'No. OpenProxyAI does not resell tokens. You pay your model providers directly and the gateway does not mark that up. Plan prices are flat.' },
  { q: 'Is there a hosted version?', a: 'No. OpenProxyAI runs in your own environment, with your own AI provider accounts.' },
  { q: 'What does the Community plan limit?', a: 'Three users, five access keys, seven days of audit history, no changes to personal-data settings or compliance templates, and no single sign-on or user provisioning. Every other capability works as on the paid plans.' },
  { q: 'What happens when a limit is reached?', a: 'The software refuses the action and says which limit applies. It does not slow down your AI traffic to enforce a plan.' },
  { q: 'Can I buy a plan online?', a: 'Not today. Paid plans are arranged directly. Book a call from the plans above.' },
];

export default function PricingFaqSection() {
  return (
    <Section id="faq" label="Billing" title={<>Questions about plans, <em>plainly answered.</em></>}>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {FAQS.map((f, i) => (
          <div key={f.q} style={{ padding: '14px 0', borderBottom: i < FAQS.length - 1 ? '1px solid var(--line)' : 'none' }}>
            <h3 style={{ margin: '0 0 6px', color: 'var(--ink)', fontSize: 14, fontWeight: 500 }}>{f.q}</h3>
            <p style={{ margin: 0, color: 'var(--ink-2)', fontFamily: 'var(--sans)', fontSize: 14, lineHeight: 1.6 }}>{f.a}</p>
          </div>
        ))}
      </div>
    </Section>
  );
}
