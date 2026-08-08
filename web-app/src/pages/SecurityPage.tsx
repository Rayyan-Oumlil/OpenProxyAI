import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import ComplianceSection from '../sections/ComplianceSection';
import BudgetsPoliciesSection from '../sections/BudgetsPoliciesSection';

export default function SecurityPage() {
  useEffect(() => { document.title = 'Security · OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Security"
        title={<>Know exactly what your team asked AI, <span style={{ color: 'var(--accent)' }}>every time.</span></>}
        description="Every request is logged, every policy is enforced before the call leaves your network, and every org's data is isolated at the database level. This is what's actually running — not a marketing claim."
      />
      <ComplianceSection />
      <BudgetsPoliciesSection />
    </>
  );
}
