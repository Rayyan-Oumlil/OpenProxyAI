import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import ComplianceSection from '../sections/ComplianceSection';
import AuditTrailSection from '../sections/AuditTrailSection';
import AccessControlSection from '../sections/AccessControlSection';

export default function SecurityPage() {
  useEffect(() => { document.title = 'Security · OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Security"
        title={<>Know exactly what your team asked AI, <span style={{ color: 'var(--accent)' }}>every time.</span></>}
        description="Compliance templates, what an actual audit log entry looks like, and how access is controlled — beyond the guardrail summary on the homepage."
      />
      <ComplianceSection />
      <AuditTrailSection />
      <AccessControlSection />
    </>
  );
}
