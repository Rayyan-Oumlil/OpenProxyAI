import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import CodeBlock from '../components/CodeBlock';
import ControlsSection from '../sections/ControlsSection';
import LimitsSection from '../sections/LimitsSection';
import ComplianceSection from '../sections/ComplianceSection';
import AuditTrailSection from '../sections/AuditTrailSection';
import AccessControlSection from '../sections/AccessControlSection';
import RegulationSection from '../sections/RegulationSection';
import VerifySection from '../sections/VerifySection';

function PostureVisual() {
  return (
    <CodeBlock title="posture, in four lines" tag="no badges">
      <span className="tok-ok">✓</span>{' self-hosted, Apache-2.0, readable\n'}
      <span className="tok-ok">✓</span>{' append-only audit trail, row-level isolation\n'}
      <span className="tok-bad">×</span>{' no SOC 2, ISO 27001 or HIPAA certification\n'}
      <span className="tok-bad">×</span>{' templates help document controls; they do not certify'}
    </CodeBlock>
  );
}

export default function SecurityPage() {
  useEffect(() => { document.title = 'Security and compliance | OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Security"
        title={<>What a reviewer can check, <span style={{ color: 'var(--accent)' }}>without a sales call.</span></>}
        description="What each control does and where to verify it, what OpenProxyAI does not claim, and how to run it yourself. We say what is and is not certified, and we link every claim to a doc, a test or the code."
        visual={<PostureVisual />}
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
