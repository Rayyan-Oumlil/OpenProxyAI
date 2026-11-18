import Section from '../components/Section';
import { PLANS, yesNo } from '../lib/plans';

const cap = (s: string): string => s.charAt(0).toUpperCase() + s.slice(1);

export default function PlansTableSection() {
  const rows: Array<[string, (p: (typeof PLANS)[number]) => string]> = [
    ['Users', p => p.users],
    ['Access keys', p => p.keys],
    ['Days of audit history', p => p.retention.replace(' days', '')],
    ['Personal-data settings and compliance templates', p => cap(yesNo(p.pii))],
    ['Single sign-on and user provisioning', p => cap(yesNo(p.sso))],
    ['Price', p => `${p.price} ${p.period}`],
  ];
  return (
    <Section id="compare-plans" label="Plans in detail" title="What each plan includes." aside="Everything not listed here is the same on every plan.">
      <div className="tbl-scroll">
        <table className="tbl">
          <thead>
            <tr><th scope="col">What is included</th>{PLANS.map(p => <th key={p.name} scope="col">{p.name}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map(([label, f]) => (
              <tr key={label}><td>{label}</td>{PLANS.map(p => <td key={p.name}>{f(p)}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  );
}
