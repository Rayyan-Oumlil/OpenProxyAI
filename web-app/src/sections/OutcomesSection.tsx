import { ShieldCheck, Wallet, ScrollText } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import Section from '../components/Section';

interface Outcome {
  icon: LucideIcon;
  title: string;
  text: string;
}

const OUTCOMES: Outcome[] = [
  { icon: ShieldCheck, title: 'Keep sensitive data where it belongs', text: 'Personal and confidential information is detected before it leaves your company. Each level of sensitivity can only reach the AI models you approved for it, and a refused request is never quietly sent elsewhere.' },
  { icon: Wallet, title: 'Keep AI agents on approved tools', text: 'Agents can only use the business tools you approved, grouped per team or application. If a tool changes after approval, it is blocked until someone reviews it.' },
  { icon: ScrollText, title: 'Prove it to your auditors', text: 'Every request, tool call, decision and refusal is recorded and can be exported to your security tools. When an auditor asks, you can answer.' },
];

export default function OutcomesSection() {
  return (
    <Section id="outcomes" label="Why OpenProxyAI" title={<>AI adoption is moving faster than <em>oversight.</em></>} aside="three results that matter">
      <p className="lede" style={{ marginBottom: 28 }}>
        Employees and applications already send company data to AI models. OpenProxyAI gives you one place to set the rules, see the activity and answer hard questions.
      </p>
      <div className="grid-3">
        {OUTCOMES.map(o => (
          <div key={o.title} className="opa-card" style={{ padding: 24 }}>
            <span style={{ width: 40, height: 40, borderRadius: 10, background: 'color-mix(in srgb, var(--accent) 12%, var(--bg))', color: 'var(--accent)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: 14 }}>
              <o.icon size={21} aria-hidden="true" />
            </span>
            <h3 style={{ margin: '0 0 8px', color: 'var(--ink)', fontSize: 17, fontWeight: 600 }}>{o.title}</h3>
            <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 15, lineHeight: 1.6, color: 'var(--ink-2)' }}>{o.text}</p>
          </div>
        ))}
      </div>
    </Section>
  );
}
