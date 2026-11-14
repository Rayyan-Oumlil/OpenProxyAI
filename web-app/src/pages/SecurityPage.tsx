import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import ComplianceSection from '../sections/ComplianceSection';
import AuditTrailSection from '../sections/AuditTrailSection';
import AccessControlSection from '../sections/AccessControlSection';

function AuditPreviewVisual() {
  return (
    <div className="opa-card" style={{ overflow: 'hidden' }}>
      <div className="opa-card-head"><span>audit_log · example entry</span><span style={{ color: 'var(--accent)' }}>append-only</span></div>
      <pre style={{ padding: 16, fontSize: 12, lineHeight: 1.8, color: 'var(--ink)', margin: 0 }}>
        <span style={{ color: 'var(--ink-3)' }}>request_id</span>{'  req_01J3K9A2XM\n'}
        <span style={{ color: 'var(--ink-3)' }}>policy</span>{'      enforce · pass\n'}
        <span style={{ color: 'var(--accent)' }}>replay</span>{'      open the trace'}<span className="term-cursor" />
      </pre>
    </div>
  );
}

export default function SecurityPage() {
  useEffect(() => { document.title = 'Security and compliance | OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Security"
        title={<>Know exactly what your team asked AI, <span style={{ color: 'var(--accent)' }}>every time.</span></>}
        description="Compliance templates, what an actual audit log entry looks like, and how access is controlled — beyond the guardrail summary on the homepage."
        visual={<AuditPreviewVisual />}
      />
      <ComplianceSection />
      <AuditTrailSection />
      <AccessControlSection />
    </>
  );
}
