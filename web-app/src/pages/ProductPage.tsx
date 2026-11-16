import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import ChecklistCard from '../components/ChecklistCard';
import ArchitectureSection from '../sections/ArchitectureSection';
import RoutingDetailSection from '../sections/RoutingDetailSection';
import BudgetsPoliciesSection from '../sections/BudgetsPoliciesSection';
import TeamsSection from '../sections/TeamsSection';
import CachingSection from '../sections/CachingSection';
import EvalSection from '../sections/EvalSection';
import ObservabilitySection from '../sections/ObservabilitySection';

export default function ProductPage() {
  useEffect(() => { document.title = 'Product | OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Product"
        title={<>How OpenProxyAI <span style={{ color: 'var(--accent)' }}>works.</span></>}
        description="One layer that checks every AI request against your rules, protects sensitive data, controls cost, and keeps a record. It runs in your own environment."
        visual={
          <ChecklistCard
            title="Every request, in this order"
            items={[
              { text: 'Who is asking?', ok: true },
              { text: 'Are they within limits?', ok: true },
              { text: 'Does your policy allow it?', ok: true },
              { text: 'Has it already been answered?', ok: true },
              { text: 'Which approved model should handle it?', ok: true },
              { text: 'Record everything, after the answer', ok: true },
            ]}
          />
        }
      />
      <ArchitectureSection />
      <RoutingDetailSection />
      <BudgetsPoliciesSection />
      <TeamsSection />
      <CachingSection />
      <EvalSection />
      <ObservabilitySection />
    </>
  );
}
