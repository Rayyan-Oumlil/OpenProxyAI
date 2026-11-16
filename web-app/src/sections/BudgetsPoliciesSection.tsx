import Section from '../components/Section';

const BUDGETS = [
  { team: 'eng-platform', pct: 78, s: 'ok',   amt: '$641 / $820' },
  { team: 'support-bot',  pct: 48, s: 'ok',   amt: '$284 / $600' },
  { team: 'research',     pct: 84, s: 'warn', amt: '$188 / $225' },
  { team: 'finance',      pct: 22, s: 'ok',   amt: '$102 / $450' },
  { team: 'ext-partner',  pct: 96, s: 'err',  amt: '$69 / $72'   },
  { team: 'marketing',    pct: 42, s: 'ok',   amt: '$38 / $90'   },
];

// The organization policy, in the order the checks run. One mode (off, log_only or enforce) covers all of them.
const POLICIES = [
  { name: 'model allowlist',     desc: 'exact model names' },
  { name: 'blocked keywords',    desc: 'case-insensitive match' },
  { name: 'PII detection',       desc: 'email · SSN · card, or Presidio' },
  { name: 'prompt injection',    desc: 'classifier, or regex fallback' },
  { name: 'response guardrails', desc: 'keywords · PII redacted in output' },
  { name: 'MCP tool lists',      desc: 'allow and block patterns' },
];

function statColor(s: string): string {
  if (s === 'err') return 'var(--err)';
  if (s === 'warn') return 'var(--warn)';
  return 'var(--accent)';
}

function Gauge({ pct, color }: { pct: number; color: string }) {
  const size = 68, stroke = 5, r = (size - stroke) / 2, c = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} role="img" aria-label={`${pct} percent of budget used`}>
      <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--line)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeDasharray={c} strokeDashoffset={c - (pct / 100) * c} strokeLinecap="round" />
      </g>
      <text x="50%" y="50%" textAnchor="middle" dominantBaseline="central" fontSize="13" fill="var(--ink)" fontFamily="var(--mono)">{pct}</text>
    </svg>
  );
}

export default function BudgetsPoliciesSection() {
  return (
    <Section id="budgets" label="§03 · budgets · policies" title={<>Cost controls and guardrails, <em>per team, per model.</em></>} aside="enforce or log only">
      <div className="split">
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 18, fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.14em' }}>
            <span>budgets · example data</span><span>illustrative values</span>
          </div>
          <div className="grid-3" style={{ gap: 20 }}>
            {BUDGETS.map(b => (
              <div key={b.team} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, textAlign: 'center' }}>
                <Gauge pct={b.pct} color={statColor(b.s)} />
                <span style={{ fontSize: 12, color: 'var(--ink)' }}>{b.team}</span>
                <span style={{ fontSize: 10.5, color: 'var(--ink-3)' }}>{b.amt}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="opa-card">
          <div className="opa-card-head"><span>organization policy</span><span>off · log_only · enforce</span></div>
          <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
            {POLICIES.map((p, i) => (
              <div key={p.name} className="policy-row" style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', gap: '4px 10px', padding: 8, border: '1px solid var(--line)', borderRadius: 6, background: 'var(--panel-2)' }}>
                <span style={{ color: 'var(--accent)' }}>{p.name}</span>
                <span style={{ fontSize: 10.5, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>step {i + 1}</span>
                <span style={{ color: 'var(--ink-3)', flexBasis: '100%' }}>{p.desc}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Section>
  );
}
