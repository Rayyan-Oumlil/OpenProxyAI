import { useRef, useLayoutEffect } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { ArrowRight, Terminal } from 'lucide-react';

gsap.registerPlugin(ScrollTrigger);

export default function HeroSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const eyebrowRef = useRef<HTMLDivElement>(null);
  const h1Ref = useRef<HTMLHeadingElement>(null);
  const subRef = useRef<HTMLParagraphElement>(null);
  const ctaRef = useRef<HTMLDivElement>(null);
  const codeRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const section = sectionRef.current;
    const content = contentRef.current;
    const eyebrow = eyebrowRef.current;
    const h1 = h1Ref.current;
    const sub = subRef.current;
    const cta = ctaRef.current;
    const code = codeRef.current;

    if (!section || !content || !eyebrow || !h1 || !sub || !cta || !code) return;

    const ctx = gsap.context(() => {
      // Load animation timeline
      const loadTl = gsap.timeline({ defaults: { ease: 'power3.out' } });

      loadTl
        .fromTo(eyebrow, { y: -12, opacity: 0 }, { y: 0, opacity: 1, duration: 0.35 }, 0.2)
        .fromTo(h1.querySelectorAll('.word'), { y: 28, opacity: 0 }, { y: 0, opacity: 1, stagger: 0.06, duration: 0.6 }, 0.35)
        .fromTo(sub, { y: 16, opacity: 0 }, { y: 0, opacity: 1, duration: 0.4 }, 0.6)
        .fromTo(cta.children, { scale: 0.96, opacity: 0 }, { scale: 1, opacity: 1, stagger: 0.08, duration: 0.35 }, 0.75)
        .fromTo(code, { y: 18, opacity: 0 }, { y: 0, opacity: 1, duration: 0.45 }, 0.9);

      // Scroll-driven exit animation
      const scrollTl = gsap.timeline({
        scrollTrigger: {
          trigger: section,
          start: 'top top',
          end: '+=130%',
          pin: true,
          scrub: 0.6,
          onLeaveBack: () => {
            // Reset all elements when scrolling back to top
            gsap.set([eyebrow, h1, sub, cta, code], { opacity: 1, y: 0, x: 0 });
          }
        }
      });

      // EXIT phase (70% - 100%)
      scrollTl
        .fromTo(content, 
          { y: 0, opacity: 1 }, 
          { y: '-18vh', opacity: 0, ease: 'power2.in' }, 
          0.7
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
          src="/images/hero_street_neon.jpg"
          alt="Cyberpunk city"
          className="w-full h-full object-cover"
        />
        <div className="bg-overlay" />
      </div>

      {/* Content */}
      <div
        ref={contentRef}
        className="relative z-10 flex flex-col items-center justify-center min-h-screen px-6 pt-20"
      >
        <div className="max-w-[1100px] w-full text-center">
          {/* Eyebrow */}
          <div ref={eyebrowRef} className="eyebrow-pill text-[#B6FF2E] mb-6">
            Zero Trust AI Gateway
          </div>

          {/* H1 */}
          <h1
            ref={h1Ref}
            className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold text-[#F2F5F9] mb-6"
          >
            <span className="word inline-block">One</span>{' '}
            <span className="word inline-block">API.</span>{' '}
            <span className="word inline-block">Every</span>{' '}
            <span className="word inline-block">Model.</span>{' '}
            <span className="word inline-block text-[#B6FF2E]">Total</span>{' '}
            <span className="word inline-block text-[#B6FF2E]">Control.</span>
          </h1>

          {/* Subheadline */}
          <p
            ref={subRef}
            className="text-lg md:text-xl text-[#A7AFBA] max-w-[52ch] mx-auto mb-8"
          >
            The secure AI gateway for regulated enterprises. Enforce policies, redact PII, 
            and audit every LLM request — across 1600+ models, from one endpoint.
          </p>

          {/* CTAs */}
          <div ref={ctaRef} className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-8">
            <a href="#" className="btn-primary group">
              Book a demo
              <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
            </a>
            <a href="#" className="btn-secondary">
              Start free trial
            </a>
          </div>

          {/* Code Snippet */}
          <div ref={codeRef} className="glass-card mx-auto max-w-[720px] p-5 text-left">
            <div className="flex items-center gap-2 mb-3">
              <Terminal className="w-4 h-4 text-[#B6FF2E]" />
              <span className="text-xs text-[#A7AFBA] mono">cURL</span>
            </div>
            <pre className="text-xs sm:text-sm text-[#F2F5F9] mono overflow-x-auto">
              <code>{`curl -X POST https://api.openproxy.ai/v1/chat/completions \\
  -H "Authorization: Bearer $KEY" \\
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"Hello"}]}'`}</code>
            </pre>
          </div>
        </div>
      </div>
    </section>
  );
}
