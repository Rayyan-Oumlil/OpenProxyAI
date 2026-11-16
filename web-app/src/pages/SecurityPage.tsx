import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import ChecklistCard from '../components/ChecklistCard';
import ControlsSection from '../sections/ControlsSection';
import LimitsSection from '../sections/LimitsSection';
import ComplianceSection from '../sections/ComplianceSection';
import AuditTrailSection from '../sections/AuditTrailSection';
import AccessControlSection from '../sections/AccessControlSection';
import RegulationSection from '../sections/RegulationSection';
import VerifySection from '../sections/VerifySection';

export default function SecurityPage() {
  useEffect(() => { document.title = 'Security and compliance | OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Security"
        title={<>What your reviewers need, <span style={{ color: 'var(--accent)' }}>without a sales call.</span></>}
        description="What each control does and where to verify it, what OpenProxyAI does not claim, and how your team can test it. We say what is and is not certified, and we link every claim to a document, a test or the code."
        visual={
          <ChecklistCard
            title="Our posture, in four lines"
            items={[
              { text: 'Open source, and it runs in your own environment', ok: true },
              { text: 'Permanent record, with each organization’s data kept apart', ok: true },
              { text: 'No SOC 2, ISO 27001 or HIPAA certification', ok: false },
              { text: 'Templates help you document controls. They do not certify.', ok: false },
            ]}
          />
        }
      />
      <ControlsSection />
      <LimitsSection />
      <ComplianceSection />
      <AuditTrailSection />
      <AccessControlSection />
      <RegulationSection />
      <VerifySection />
    </>
  );
}
