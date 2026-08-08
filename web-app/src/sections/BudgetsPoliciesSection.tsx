import { PAGE_MAX_WIDTH } from '../lib/layout';

const BUDGETS = [
  { team: 'eng-platform', pct: 78, s: 'ok',   amt: '$641 / $820' },
  { team: 'support-bot',  pct: 48, s: 'ok',   amt: '$284 / $600' },
  { team: 'research',     pct: 84, s: 'warn',  amt: '$188 / $225' },
  { team: 'finance',      pct: 22, s: 'ok',   amt: '$102 / $450' },
  { team: 'ext-partner',  pct: 96, s: 'err',  amt: '$69 / $72'   },
  { team: 'marketing',    pct: 42, s: 'ok',   amt: '$38 / $90'   },
];

const POLICIES = [
  { name: 'pii_redact',   mode: 'enforce',  desc: 'regex + dlp-v4',       hits: 1842, s: 'ok'   },
  { name: 'secrets_scan', mode: 'enforce',  desc: 'response side',          hits: 611, s: 'ok'   },
  { name: 'topic_guard',  mode: 'enforce',  desc: 'legal·medical·harm',     hits: 248, s: 'ok'   },
  { name: 'injection',    mode: 'enforce',  desc: 'score > 0.8 block',       hits: 57, s: 'ok'   },
  { name: 'model_allow',  mode: 'enforce',  desc: 'gpt-4o,claude·sonnet',    hits: 33, s: 'ok'   },
  { name: 'jailbreak_lm', mode: 'log-only', desc: 'small classifier',         hits: 9,  s: 'warn' },
];

function barColor(s: string) {
  if (s === 'err')  return 'var(--err)';
  if (s === 'warn') return 'var(--warn)';
  return 'var(--accent)';
}

export default function BudgetsPoliciesSection() {
  return (
    <section style={{ padding: '60px 0', borderTop: '1px solid var(--line)' }}>
      <div style={{ maxWidth: PAGE_MAX_WIDTH, margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr auto', gap: 24, alignItems: 'baseline', marginBottom: 32, paddingBottom: 12, borderBottom: '1px dashed var(--line)' }} className="sec-head">
          <span style={{ color: 'var(--ink-3)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.2em' }}>§03 · budgets · policies</span>
          <h2 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(26px,2.8vw,38px)', letterSpacing: '-0.025em', fontWeight: 500, margin: 0, color: 'var(--ink)' }}>
            Cost controls and guardrails — <em style={{ fontStyle: 'normal', color: 'var(--accent)' }}>per team, per model, per dollar.</em>
          </h2>
          <span style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.2em' }}>enforced · log-only available</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr', gap: 10 }} className="budget-grid">
          {/* Daily budgets */}
          <div className="opa-card">
            <div className="opa-card-head"><span>daily budgets</span><span>reset 00:00 UTC</span></div>
            <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
              {BUDGETS.map(b => (
                <div key={b.team} style={{ display: 'grid', gridTemplateColumns: '180px 1fr 130px', gap: 14, alignItems: 'center', fontSize: 12 }}>
                  <span style={{ color: 'var(--ink-2)' }}>{b.team}</span>
                  <div style={{ position: 'relative', height: 8, background: 'var(--line)', borderRadius: 4, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${b.pct}%`, background: barColor(b.s) }} />
                    <span style={{ position: 'absolute', top: -2, bottom: -2, left: '90%', width: 1, background: 'var(--ink-2)' }} />
                  </div>
                  <span style={{ textAlign: 'right', color: 'var(--ink)' }}>{b.amt}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Active policies */}
          <div className="opa-card">
            <div className="opa-card-head"><span>active policies</span><span>6 enforcing · 1 log-only</span></div>
            <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
              {POLICIES.map(p => (
                <div key={p.name} style={{
                  display: 'grid', gridTemplateColumns: '130px 80px 1fr auto', gap: 10,
                  alignItems: 'center', padding: '8px', border: '1px solid var(--line)',
                  borderRadius: 6, background: 'var(--panel-2)',
                }}>
                  <span style={{ color: p.s === 'ok' ? 'var(--accent)' : 'var(--warn)' }}>{p.name}</span>
                  <span style={{ fontSize: 10.5, color: p.mode === 'enforce' ? 'var(--accent)' : 'var(--warn)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{p.mode}</span>
                  <span style={{ color: 'var(--ink-3)' }}>{p.desc}</span>
                  <span style={{ color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>{p.hits.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 1000px) {
          .budget-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </section>
  );
}
