import { useRef, useLayoutEffect } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { ArrowRight, Shield, Eye, Filter, AlertTriangle } from 'lucide-react';

gsap.registerPlugin(ScrollTrigger);

const policies = [
  {
    icon: Eye,
    title: 'PII Redaction',
    description: 'Mask emails, phones, IDs before they leave your infra.',
  },
  {
    icon: Shield,
    title: 'Topic Guard',
    description: 'Deny requests that violate your content policy.',
  },
  {
    icon: Filter,
    title: 'Keyword Filter',
    description: 'Allowlist / denylist with regex support.',
  },
];

export default function GuardrailsSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const cardsRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const section = sectionRef.current;
    const content = contentRef.current;
    const cards = cardsRef.current;

    if (!section || !content || !cards) return;

    const textElements = content.querySelectorAll('.animate-text');
    const policyCards = cards.querySelectorAll('.policy-card');

    const ctx = gsap.context(() => {
      const scrollTl = gsap.timeline({
        scrollTrigger: {
          trigger: section,
          start: 'top top',
          end: '+=130%',
          pin: true,
          scrub: 0.6,
        }
      });

      // ENTRANCE (0% - 30%)
      scrollTl
        .fromTo(textElements, 
          { y: 24, opacity: 0 }, 
          { y: 0, opacity: 1, stagger: 0.03, ease: 'none' }, 
          0
        )
        .fromTo(policyCards, 
          { y: 35, scale: 0.96, opacity: 0 }, 
          { y: 0, scale: 1, opacity: 1, stagger: 0.04, ease: 'none' }, 
          0.12
        );

      // SETTLE (30% - 70%) - hold

      // EXIT (70% - 100%)
      scrollTl
        .fromTo(content, 
          { y: 0, opacity: 1 }, 
          { y: '-14vh', opacity: 0, ease: 'power2.in' }, 
          0.7
        )
        .fromTo(cards, 
          { y: 0, opacity: 1 }, 
          { y: '-10vh', opacity: 0, ease: 'power2.in' }, 
          0.72
        )
        .fromTo(section.querySelector('.bg-image'), 
          { scale: 1 }, 
          { scale: 1.06, ease: 'none' }, 
          0.7
        );
    }, section);

    return () => ctx.revert();
  }, []);

  return (
    <section ref={sectionRef} className="section-pinned">
      {/* Background Image */}
      <div className="bg-image absolute inset-0">
        <img
          src="/images/neon_corridor.jpg"
          alt="Neon corridor"
          className="w-full h-full object-cover"
        />
        <div className="bg-overlay" />
      </div>

      {/* Content */}
      <div className="relative z-10 flex items-center justify-center min-h-screen px-6">
        <div className="max-w-[980px] w-full text-center">
          <div ref={contentRef}>
            <div className="animate-text eyebrow-pill text-[#B6FF2E] mb-4 inline-flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              Guardrails
            </div>
            <h2 className="animate-text text-3xl sm:text-4xl lg:text-5xl font-bold text-[#F2F5F9] mb-4">
              Block the bad.<br />
              <span className="text-[#B6FF2E]">Keep the useful.</span>
            </h2>
            <p className="animate-text text-base lg:text-lg text-[#A7AFBA] max-w-[60ch] mx-auto mb-10">
              PII redaction, topic filters, and keyword guards—evaluated in 
              milliseconds before the request reaches the model.
            </p>
          </div>

          {/* Policy Cards */}
          <div ref={cardsRef} className="grid grid-cols-1 md:grid-cols-3 gap-4 lg:gap-6 mb-8">
            {policies.map((policy, index) => (
              <div
                key={index}
                className="policy-card glass-card p-6 text-left hover:border-[#B6FF2E]/30 transition-all cursor-pointer group"
              >
                <div className="w-12 h-12 rounded-xl bg-[#B6FF2E]/10 flex items-center justify-center mb-4 group-hover:bg-[#B6FF2E]/20 transition-colors">
                  <policy.icon className="w-6 h-6 text-[#B6FF2E]" />
                </div>
                <h3 className="text-lg font-semibold text-[#F2F5F9] mb-2">
                  {policy.title}
                </h3>
                <p className="text-sm text-[#A7AFBA]">
                  {policy.description}
                </p>
              </div>
            ))}
          </div>

          <a href="#" className="btn-secondary group inline-flex">
            Read the guardrails guide
            <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
          </a>
        </div>
      </div>
    </section>
  );
}
