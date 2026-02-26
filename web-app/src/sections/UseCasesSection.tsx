import { useRef, useLayoutEffect } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { ArrowUpRight, TrendingUp, HeartPulse, Landmark } from 'lucide-react';

gsap.registerPlugin(ScrollTrigger);

const useCases = [
  {
    icon: TrendingUp,
    title: 'Financial Services',
    description: 'Meet SOC 2 and regulatory requirements. Enforce PII redaction on every prompt. Full audit trail per user, per model.',
  },
  {
    icon: HeartPulse,
    title: 'Healthcare & Life Sciences',
    description: 'HIPAA-ready guardrails that strip PHI before it reaches any LLM. Control which models clinicians and researchers can access.',
  },
  {
    icon: Landmark,
    title: 'Government & Public Sector',
    description: 'Air-gapped and on-prem deployment options. RBAC aligned to agency roles. Immutable audit logs with 90-day retention.',
  },
];

export default function UseCasesSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);
  const cardsRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const section = sectionRef.current;
    const header = headerRef.current;
    const cards = cardsRef.current;

    if (!section || !header || !cards) return;

    const cardElements = cards.querySelectorAll('.use-case-card');

    const ctx = gsap.context(() => {
      // Header animation
      gsap.fromTo(header,
        { y: 18, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          duration: 0.6,
          scrollTrigger: {
            trigger: header,
            start: 'top 80%',
            end: 'top 55%',
            scrub: true,
          }
        }
      );

      // Cards animation
      gsap.fromTo(cardElements,
        { y: 28, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          stagger: 0.12,
          duration: 0.6,
          scrollTrigger: {
            trigger: cards,
            start: 'top 75%',
            end: 'top 50%',
            scrub: true,
          }
        }
      );

      // Parallax background
      gsap.fromTo(section.querySelector('.bg-image'),
        { y: 0 },
        {
          y: -18,
          ease: 'none',
          scrollTrigger: {
            trigger: section,
            start: 'top bottom',
            end: 'bottom top',
            scrub: true,
          }
        }
      );
    }, section);

    return () => ctx.revert();
  }, []);

  return (
    <section ref={sectionRef} className="relative py-20 lg:py-28">
      {/* Background Image */}
      <div className="bg-image absolute inset-0">
        <img
          src="/images/night_city_street.jpg"
          alt="Night city street"
          className="w-full h-full object-cover"
        />
        <div className="bg-overlay" />
      </div>

      {/* Content */}
      <div className="relative z-10 px-6 lg:px-[9vw]">
        {/* Header */}
        <div ref={headerRef} className="text-center mb-12">
          <div className="eyebrow-pill text-[#B6FF2E] mb-4 inline-block">
            Use Cases
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-[#F2F5F9] mb-4">
            Built for <span className="text-[#B6FF2E]">regulated industries</span>
          </h2>
          <p className="text-base lg:text-lg text-[#A7AFBA] max-w-[50ch] mx-auto">
            Deploy AI across your organization without compromising compliance or security.
          </p>
        </div>

        {/* Cards */}
        <div ref={cardsRef} className="grid grid-cols-1 md:grid-cols-3 gap-4 lg:gap-6 max-w-[1200px] mx-auto">
          {useCases.map((useCase, index) => (
            <div
              key={index}
              className="use-case-card glass-card p-6 group cursor-pointer transition-all duration-300 hover:-translate-y-1.5 hover:border-white/[0.18]"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="w-12 h-12 rounded-xl bg-[#B6FF2E]/10 flex items-center justify-center group-hover:bg-[#B6FF2E]/20 transition-colors">
                  <useCase.icon className="w-6 h-6 text-[#B6FF2E]" />
                </div>
                <ArrowUpRight className="w-5 h-5 text-[#A7AFBA] group-hover:text-[#B6FF2E] group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-all" />
              </div>
              <h3 className="text-lg font-semibold text-[#F2F5F9] mb-2">
                {useCase.title}
              </h3>
              <p className="text-sm text-[#A7AFBA]">
                {useCase.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
