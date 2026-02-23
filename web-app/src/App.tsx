import { useEffect } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import Navigation from './components/Navigation';
import HeroSection from './sections/HeroSection';
import UnifiedApiSection from './sections/UnifiedApiSection';
import ObservabilitySection from './sections/ObservabilitySection';
import GuardrailsSection from './sections/GuardrailsSection';
import EnterpriseSecuritySection from './sections/EnterpriseSecuritySection';
import UseCasesSection from './sections/UseCasesSection';
import TestimonialsSection from './sections/TestimonialsSection';
import PricingSection from './sections/PricingSection';
import FooterSection from './sections/FooterSection';
import './App.css';

gsap.registerPlugin(ScrollTrigger);

function App() {
  useEffect(() => {
    // Wait for all ScrollTriggers to be created
    const timeout = setTimeout(() => {
      const pinned = ScrollTrigger.getAll()
        .filter(st => st.vars.pin)
        .sort((a, b) => a.start - b.start);
      
      const maxScroll = ScrollTrigger.maxScroll(window);
      
      if (!maxScroll || pinned.length === 0) return;

      // Build ranges and snap targets from pinned sections
      const pinnedRanges = pinned.map(st => ({
        start: st.start / maxScroll,
        end: (st.end ?? st.start) / maxScroll,
        center: (st.start + ((st.end ?? st.start) - st.start) * 0.5) / maxScroll,
      }));

      // Create global snap
      ScrollTrigger.create({
        snap: {
          snapTo: (value: number) => {
            // Check if within any pinned range (with buffer)
            const inPinned = pinnedRanges.some(
              r => value >= r.start - 0.08 && value <= r.end + 0.08
            );
            
            if (!inPinned) return value; // Flowing section: free scroll

            // Find nearest pinned center
            const target = pinnedRanges.reduce(
              (closest, r) =>
                Math.abs(r.center - value) < Math.abs(closest - value)
                  ? r.center
                  : closest,
              pinnedRanges[0]?.center ?? 0
            );

            return target;
          },
          duration: { min: 0.15, max: 0.35 },
          delay: 0,
          ease: 'power2.out',
        },
      });
    }, 100);

    return () => {
      clearTimeout(timeout);
      ScrollTrigger.getAll().forEach(st => st.kill());
    };
  }, []);

  return (
    <div className="relative bg-[#0B0C0F] min-h-screen">
      {/* Grain Overlay */}
      <div className="grain-overlay" />
      
      {/* Navigation */}
      <Navigation />
      
      {/* Main Content */}
      <main className="relative">
        {/* Section 1: Hero - pin: true */}
        <HeroSection />
        
        {/* Section 2: Unified API - pin: true */}
        <UnifiedApiSection />
        
        {/* Section 3: Observability - pin: true */}
        <ObservabilitySection />
        
        {/* Section 4: Guardrails - pin: true */}
        <GuardrailsSection />
        
        {/* Section 5: Enterprise Security - pin: true */}
        <EnterpriseSecuritySection />
        
        {/* Section 6: Use Cases - pin: false */}
        <UseCasesSection />
        
        {/* Section 7: Testimonials - pin: false */}
        <TestimonialsSection />
        
        {/* Section 8: Pricing - pin: false */}
        <PricingSection />
        
        {/* Section 9: Footer - pin: false */}
        <FooterSection />
      </main>
    </div>
  );
}

export default App;
