import { useRef, useLayoutEffect } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { ArrowRight, Key, Wallet, FileCheck, Users, Shield } from 'lucide-react';

gsap.registerPlugin(ScrollTrigger);

const securityFeatures = [
  {
    icon: Users,
    label: 'SSO',
    description: 'SAML / OIDC',
  },
  {
    icon: Wallet,
    label: 'SCIM',
    description: 'Automated provisioning',
  },
  {
    icon: FileCheck,
    label: 'Audit Logs',
    description: '90-day retention',
  },
  {
    icon: Key,
    label: 'RBAC',
    description: 'Role-based access',
  },
];

export default function EnterpriseSecuritySection() {
  const sectionRef = useRef<HTMLElement>(null);
  const leftPanelRef = useRef<HTMLDivElement>(null);
  const rightCardRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const section = sectionRef.current;
    const leftPanel = leftPanelRef.current;
    const rightCard = rightCardRef.current;

    if (!section || !leftPanel || !rightCard) return;

    const rows = rightCard.querySelectorAll('.security-row');

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
        .fromTo(leftPanel, 
          { x: '-55vw', opacity: 0 }, 
          { x: 0, opacity: 1, ease: 'none' }, 
          0
        )
        .fromTo(rightCard, 
          { x: '55vw', opacity: 0 }, 
          { x: 0, opacity: 1, ease: 'none' }, 
          0.06
        )
        .fromTo(rows, 
          { y: 14, opacity: 0 }, 
          { y: 0, opacity: 1, stagger: 0.03, ease: 'none' }, 
          0.14
        );

      // SETTLE (30% - 70%) - hold

      // EXIT (70% - 100%)
      scrollTl
        .fromTo(leftPanel, 
          { x: 0, opacity: 1 }, 
          { x: '-18vw', opacity: 0, ease: 'power2.in' }, 
          0.7
        )
        .fromTo(rightCard, 
          { x: 0, opacity: 1 }, 
          { x: '18vw', opacity: 0, ease: 'power2.in' }, 
          0.7
        )
        .fromTo(section.querySelector('.bg-image'), 
          { scale: 1 }, 
          { scale: 1.05, ease: 'none' }, 
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
          src="/images/vertical_neon_street.jpg"
          alt="Vertical neon street"
          className="w-full h-full object-cover"
        />
        <div className="bg-overlay" />
      </div>

      {/* Content */}
      <div className="relative z-10 flex items-center min-h-screen px-6 lg:px-[9vw]">
        <div className="w-full flex flex-col lg:flex-row items-center justify-between gap-10 lg:gap-16">
          {/* Left Panel */}
          <div ref={leftPanelRef} className="w-full lg:w-[min(40vw,520px)]">
            <div className="eyebrow-pill text-[#B6FF2E] mb-4 inline-flex items-center gap-2">
              <Shield className="w-4 h-4" />
              Enterprise Security
            </div>
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-[#F2F5F9] mb-4">
              Built for<br />
              <span className="text-[#B6FF2E]">regulated teams.</span>
            </h2>
            <p className="text-base lg:text-lg text-[#A7AFBA] mb-6">
              SSO, SCIM, audit logs, and fine-grained RBAC—so you can ship AI 
              features without shipping risk.
            </p>
            <ul className="space-y-3 mb-8">
              <li className="flex items-start gap-3">
                <Key className="w-5 h-5 text-[#B6FF2E] mt-0.5 flex-shrink-0" />
                <span className="text-sm text-[#A7AFBA]">Virtual keys with scoped permissions</span>
              </li>
              <li className="flex items-start gap-3">
                <Wallet className="w-5 h-5 text-[#B6FF2E] mt-0.5 flex-shrink-0" />
                <span className="text-sm text-[#A7AFBA]">Budget caps per team / project</span>
              </li>
              <li className="flex items-start gap-3">
                <FileCheck className="w-5 h-5 text-[#B6FF2E] mt-0.5 flex-shrink-0" />
                <span className="text-sm text-[#A7AFBA]">SOC 2 Type II & GDPR-ready</span>
              </li>
            </ul>
            <a href="#" className="btn-primary group inline-flex">
              Contact sales
              <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
            </a>
          </div>

          {/* Right Card */}
          <div ref={rightCardRef} className="glass-card w-full lg:w-[min(34vw,420px)] p-6 relative">
            {/* Shield Icon */}
            <div className="absolute top-4 right-4">
              <Shield className="w-8 h-8 text-[#B6FF2E]/30" />
            </div>

            <h3 className="text-lg font-semibold text-[#F2F5F9] mb-4 pr-10">
              Security Stack
            </h3>

            <div className="space-y-0">
              {securityFeatures.map((feature, index) => (
                <div
                  key={index}
                  className="security-row flex items-center gap-4 py-4 border-b border-white/10 last:border-b-0"
                >
                  <div className="w-10 h-10 rounded-lg bg-[#B6FF2E]/10 flex items-center justify-center flex-shrink-0">
                    <feature.icon className="w-5 h-5 text-[#B6FF2E]" />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-[#F2F5F9]">
                      {feature.label}
                    </div>
                    <div className="text-xs text-[#A7AFBA]">
                      {feature.description}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
