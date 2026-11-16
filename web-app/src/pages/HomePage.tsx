import { useEffect } from 'react';
import HeroSection from '../sections/HeroSection';
import TrustStrip from '../sections/TrustStrip';
import ProblemSection from '../sections/ProblemSection';
import ProofSection from '../sections/ProofSection';
import McpSection from '../sections/McpSection';
import DeploySection from '../sections/DeploySection';
import PipelineSection from '../sections/PipelineSection';
import EvidenceSection from '../sections/EvidenceSection';
import CompareTeaser from '../sections/CompareTeaser';
import FinalCtaSection from '../sections/FinalCtaSection';

export default function HomePage() {
  useEffect(() => { document.title = 'OpenProxyAI | The LLM gateway for teams that must prove what their AI did'; }, []);

  return (
    <>
      <HeroSection />
      <TrustStrip />
      <ProblemSection />
      <ProofSection />
      <McpSection />
      <DeploySection />
      <PipelineSection />
      <EvidenceSection />
      <CompareTeaser />
      <FinalCtaSection />
    </>
  );
}
