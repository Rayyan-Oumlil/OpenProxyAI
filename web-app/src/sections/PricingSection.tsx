import { useRef, useLayoutEffect } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { Check, ArrowRight, Sparkles } from 'lucide-react';

gsap.registerPlugin(ScrollTrigger);

const plans = [
  {
    name: 'Developer',
    price: 'Free',
    description: 'Evaluate the platform with your team — no credit card required',
    features: [
      '100K requests/mo',
      'Community support',
      'Basic observability',
      '3 team members',
      'Standard caching',
    ],
    cta: 'Start evaluating',
    featured: false,
  },
  {
    name: 'Team',
    price: '$49',
    period: '/mo',
    description: 'For security-conscious teams deploying AI in production',
    features: [
      'Unlimited requests',
      'Priority support',
      'SSO & SCIM',
      'Unlimited team members',
      'Advanced caching',
      'Custom guardrails',
    ],
    cta: 'Start free trial',
    featured: true,
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    description: 'For organizations with advanced needs',
    features: [
      'Dedicated support',
      '99.99% SLA',
      'Audit logs',
      'Custom contracts',
      'On-prem option',
      'Security reviews',
    ],
    cta: 'Contact sales',
    featured: false,
  },
];

export default function PricingSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);
  const cardsRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const section = sectionRef.current;
    const header = headerRef.current;
    const cards = cardsRef.current;

    if (!section || !header || !cards) return;

    const cardElements = cards.querySelectorAll('.pricing-card');

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
        { y: 32, opacity: 0 },
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
    }, section);

    return () => ctx.revert();
  }, []);

  return (
    <section ref={sectionRef} className="relative py-20 lg:py-28" id="pricing">
      {/* Background Image */}
      <div className="bg-image absolute inset-0">
        <img
          src="/images/rainy_street_neon.jpg"
          alt="Rainy street"
          className="w-full h-full object-cover"
        />
        <div className="bg-overlay" />
      </div>

      {/* Content */}
      <div className="relative z-10 px-6 lg:px-[9vw]">
        {/* Header */}
        <div ref={headerRef} className="text-center mb-12">
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-[#F2F5F9] mb-4">
            Start free. <span className="text-[#B6FF2E]">Scale predictably.</span>
          </h2>
          <p className="text-base lg:text-lg text-[#A7AFBA] max-w-[50ch] mx-auto">
            No hidden fees. Pay for what you use—with controls to keep budgets tight.
          </p>
        </div>

        {/* Cards */}
        <div ref={cardsRef} className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-[1200px] mx-auto">
          {plans.map((plan, index) => (
            <div
              key={index}
              className={`pricing-card glass-card p-6 relative transition-all duration-300 hover:-translate-y-1.5 ${
                plan.featured 
                  ? 'border-t-[3px] border-t-[#B6FF2E] lg:-mt-4 lg:mb-4' 
                  : 'hover:border-white/[0.18]'
              }`}
            >
              {/* Featured Badge */}
              {plan.featured && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-[#B6FF2E] text-[#0B0C0F] text-xs font-medium">
                    <Sparkles className="w-3 h-3" />
                    Most popular
                  </span>
                </div>
              )}

              <div className="mb-6">
                <h3 className="text-lg font-semibold text-[#F2F5F9] mb-2">
                  {plan.name}
                </h3>
                <div className="flex items-baseline gap-1 mb-2">
                  <span className="text-3xl lg:text-4xl font-bold text-[#F2F5F9]">
                    {plan.price}
                  </span>
                  {plan.period && (
                    <span className="text-sm text-[#A7AFBA]">{plan.period}</span>
                  )}
                </div>
                <p className="text-sm text-[#A7AFBA]">{plan.description}</p>
              </div>

              <ul className="space-y-3 mb-8">
                {plan.features.map((feature, fIndex) => (
                  <li key={fIndex} className="flex items-start gap-3">
                    <Check className="w-5 h-5 text-[#B6FF2E] flex-shrink-0 mt-0.5" />
                    <span className="text-sm text-[#A7AFBA]">{feature}</span>
                  </li>
                ))}
              </ul>

              <a
                href="#"
                className={`w-full flex items-center justify-center gap-2 py-3 rounded-[14px] font-medium transition-all duration-200 ${
                  plan.featured
                    ? 'btn-primary'
                    : 'btn-secondary'
                }`}
              >
                {plan.cta}
                <ArrowRight className="w-4 h-4" />
              </a>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
