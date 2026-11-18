import { useEffect } from 'react';
import HeroSection from '../sections/HeroSection';
import MarqueeSection from '../sections/MarqueeSection';
import ControlsStory from '../sections/ControlsStory';
import HowItWorksSection from '../sections/HowItWorksSection';
import ConsoleSection from '../sections/ConsoleSection';
import QuickStartSection from '../sections/QuickStartSection';
import EvidenceSection from '../sections/EvidenceSection';
import FaqSection from '../sections/FaqSection';
import FinalCtaSection from '../sections/FinalCtaSection';

export default function HomePage() {
  useEffect(() => { document.title = 'OpenProxyAI | Sensitive data and AI agents, under your control'; }, []);

  return (
    <>
      <HeroSection />
      <MarqueeSection />
      <ControlsStory />
      <HowItWorksSection />
      <ConsoleSection />
      <EvidenceSection />
      <QuickStartSection />
      <FaqSection />
      <FinalCtaSection />
    </>
  );
}
