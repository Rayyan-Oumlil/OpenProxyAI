import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import BuildVsBuySection from '../sections/BuildVsBuySection';
import PricingFaqSection from '../sections/PricingFaqSection';

const METERED = [22, 38, 19, 61, 34, 72, 28, 45];
const FLAT_PCT = 40;

function FlatFeeVisual() {
  return (
    <div className="opa-card" style={{ padding: 18 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.14em' }}>
        <span>daily spend</span>
        <span>illustrative</span>
      </div>
      <div style={{ position: 'relative', height: 84, display: 'flex', alignItems: 'flex-end', gap: 5 }}>
        <div style={{ position: 'absolute', left: 0, right: 0, bottom: `${FLAT_PCT}%`, borderTop: '1px dashed var(--accent)' }} />
        {METERED.map((v, i) => (
          <div key={i} style={{ flex: 1, height: `${v}%`, background: 'var(--line-2)', borderRadius: '2px 2px 0 0' }} />
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 12, fontSize: 11 }}>
        <span style={{ color: 'var(--ink-3)' }}>token-metered (variable)</span>
        <span style={{ color: 'var(--accent)' }}>flat fee (yours)</span>
      </div>
    </div>
  );
}

export default function PricingPage() {
  useEffect(() => { document.title = 'Pricing · OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Pricing"
        title={<>What this replaces on <span style={{ color: 'var(--accent)' }}>your roadmap.</span></>}
        description="Plans and the flat-fee breakdown live on the homepage — this page is the build-vs-buy math and the billing questions that actually come up."
        visual={<FlatFeeVisual />}
      />
      <BuildVsBuySection />
      <PricingFaqSection />
    </>
  );
}
