import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import CodeBlock from '../components/CodeBlock';
import ArchitectureSection from '../sections/ArchitectureSection';
import RoutingDetailSection from '../sections/RoutingDetailSection';
import BudgetsPoliciesSection from '../sections/BudgetsPoliciesSection';
import CachingSection from '../sections/CachingSection';
import EvalSection from '../sections/EvalSection';
import ObservabilitySection from '../sections/ObservabilitySection';

function StageOrderVisual() {
  return (
    <CodeBlock title="every request, in this order" tag="request pipeline">
      <span className="tok-ok">1</span>{' auth          api key resolves to a user and org\n'}
      <span className="tok-ok">2</span>{' rate limit    request, token and budget limits\n'}
      <span className="tok-ok">3</span>{' policy        allow, block or log (HTTP 446 on block)\n'}
      <span className="tok-ok">4</span>{' cache         L1, L2, L3 (off by default)\n'}
      <span className="tok-ok">5</span>{' route         approved model and key for the data class\n'}
      <span className="tok-ok">6</span>{' log           written after the response, never blocks'}
    </CodeBlock>
  );
}

export default function ProductPage() {
  useEffect(() => { document.title = 'Product | OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Product"
        title={<>How the gateway <span style={{ color: 'var(--accent)' }}>works.</span></>}
        description="The architecture, how data classes decide where a request may go, budgets and policy, caching, the evaluation loop and the observability you already run."
        visual={<StageOrderVisual />}
      />
      <ArchitectureSection />
      <RoutingDetailSection />
      <BudgetsPoliciesSection />
      <CachingSection />
      <EvalSection />
      <ObservabilitySection />
    </>
  );
}
