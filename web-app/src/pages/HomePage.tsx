import { useEffect } from 'react';
import HeroSection from '../sections/HeroSection';
import TrustStrip from '../sections/TrustStrip';
import OutcomesSection from '../sections/OutcomesSection';
import ProductTourSection from '../sections/ProductTourSection';
import FeatureGrid from '../sections/FeatureGrid';
import SensitiveDataSection from '../sections/SensitiveDataSection';
import AgentsSection from '../sections/AgentsSection';
import PipelineSection from '../sections/PipelineSection';
import IndustriesSection from '../sections/IndustriesSection';
import DeploySection from '../sections/DeploySection';
import EvidenceSection from '../sections/EvidenceSection';
import CompareTeaser from '../sections/CompareTeaser';
import DocsBandSection from '../sections/DocsBandSection';
import QuickStartSection from '../sections/QuickStartSection';
import FaqSection from '../sections/FaqSection';
import FinalCtaSection from '../sections/FinalCtaSection';

export default function HomePage() {
  useEffect(() => { document.title = 'OpenProxyAI | Control and prove everything your AI does'; }, []);

  return (
    <>
      <HeroSection />
      <TrustStrip />
      <OutcomesSection />
      <ProductTourSection />
      <FeatureGrid />
      <SensitiveDataSection />
      <AgentsSection />
      <PipelineSection />
      <IndustriesSection />
      <DeploySection />
      <EvidenceSection />
      <CompareTeaser />
      <DocsBandSection />
      <QuickStartSection />
      <FaqSection />
      <FinalCtaSection />
    </>
  );
}
