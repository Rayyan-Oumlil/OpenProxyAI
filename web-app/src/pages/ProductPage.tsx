import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import ArchitectureSection from '../sections/ArchitectureSection';
import CachingSection from '../sections/CachingSection';
import ObservabilitySection from '../sections/ObservabilitySection';

const BUDGET = [
  { label: 'auth', ms: 0.2, color: 'var(--accent)' },
  { label: 'rate', ms: 0.1, color: 'var(--accent)' },
  { label: 'policy', ms: 0.8, color: 'var(--warn)' },
  { label: 'cache', ms: 0.4, color: 'var(--accent)' },
  { label: 'route', ms: 2.3, color: '#8bc6ff' },
];
const TOTAL_MS = BUDGET.reduce((sum, b) => sum + b.ms, 0);

function LatencyBudgetVisual() {
  return (
    <div className="opa-card" style={{ padding: 18 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 14 }}>
        <span style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.14em' }}>p50 overhead</span>
        <span style={{ fontFamily: 'var(--sans)', fontSize: 22, fontWeight: 500, color: 'var(--ink)' }}>{TOTAL_MS.toFixed(1)}<span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--ink-3)' }}>ms</span></span>
      </div>
      <div style={{ display: 'flex', height: 10, borderRadius: 5, overflow: 'hidden', marginBottom: 12 }}>
        {BUDGET.map(b => (
          <div key={b.label} title={`${b.label} · ${b.ms}ms`} style={{ width: `${(b.ms / TOTAL_MS) * 100}%`, background: b.color, borderRight: '1px solid var(--bg)' }} />
        ))}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 14px' }}>
        {BUDGET.map(b => (
          <span key={b.label} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--ink-3)' }}>
            <span style={{ width: 6, height: 6, borderRadius: 2, background: b.color, display: 'inline-block' }} />
            {b.label}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function ProductPage() {
  useEffect(() => { document.title = 'Product · OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Product"
        title={<>How the <span style={{ color: 'var(--accent)' }}>control plane</span> works.</>}
        description="Beyond the request pipeline on the homepage — this is the architecture, the cache, and how it plugs into the observability stack you already run."
        visual={<LatencyBudgetVisual />}
      />
      <ArchitectureSection />
      <CachingSection />
      <ObservabilitySection />
    </>
  );
}
