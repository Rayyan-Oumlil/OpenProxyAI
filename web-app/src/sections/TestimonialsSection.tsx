import { useRef, useLayoutEffect } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { Quote } from 'lucide-react';

gsap.registerPlugin(ScrollTrigger);

const testimonials = [
  {
    quote: "Our compliance team was blocking every AI initiative. openproxyAI gave us the audit logs and PII controls they needed — we went from blocked to deployed in two weeks.",
    author: 'Marcus Chen',
    role: 'VP of Security',
    company: 'Regional Investment Bank',
  },
  {
    quote: "We needed HIPAA-grade guardrails before any LLM could touch patient data. openproxyAI was the only gateway that gave us prompt-level redaction and a full chain of custody.",
    author: 'Dr. Sarah Okonkwo',
    role: 'Chief Information Security Officer',
    company: 'Healthcare Network',
  },
];

export default function TestimonialsSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);
  const cardsRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const section = sectionRef.current;
    const header = headerRef.current;
    const cards = cardsRef.current;

    if (!section || !header || !cards) return;

    const cardElements = cards.querySelectorAll('.testimonial-card');

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

      // Cards animation (from sides)
      cardElements.forEach((card, index) => {
        gsap.fromTo(card,
          { x: index === 0 ? '-6vw' : '6vw', opacity: 0 },
          {
            x: 0,
            opacity: 1,
            duration: 0.6,
            scrollTrigger: {
              trigger: cards,
              start: 'top 75%',
              end: 'top 50%',
              scrub: true,
            }
          }
        );
      });
    }, section);

    return () => ctx.revert();
  }, []);

  return (
    <section ref={sectionRef} className="relative py-20 lg:py-28">
      {/* Background Image */}
      <div className="bg-image absolute inset-0">
        <img
          src="/images/neon_alley.jpg"
          alt="Neon alley"
          className="w-full h-full object-cover"
        />
        <div className="bg-overlay" />
      </div>

      {/* Content */}
      <div className="relative z-10 px-6 lg:px-[9vw]">
        {/* Header */}
        <div ref={headerRef} className="text-center mb-12">
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-[#F2F5F9] mb-4">
            Trusted by <span className="text-[#B6FF2E]">security teams</span>
          </h2>
          <p className="text-base lg:text-lg text-[#A7AFBA] max-w-[50ch] mx-auto">
            From financial services to healthcare — teams in regulated industries rely on openproxyAI to keep AI usage compliant.
          </p>
        </div>

        {/* Cards */}
        <div ref={cardsRef} className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-[1200px] mx-auto">
          {testimonials.map((testimonial, index) => (
            <div
              key={index}
              className="testimonial-card glass-card p-8 relative"
            >
              {/* Quote Icon */}
              <div className="absolute top-6 right-6">
                <Quote className="w-8 h-8 text-[#B6FF2E]/30" />
              </div>

              <p className="text-lg lg:text-xl text-[#F2F5F9] mb-6 leading-relaxed">
                "{testimonial.quote}"
              </p>

              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-[#B6FF2E]/10 flex items-center justify-center flex-shrink-0">
                  <span className="text-sm font-medium text-[#B6FF2E]">
                    {testimonial.author.charAt(0)}
                  </span>
                </div>
                <div>
                  <div className="text-sm font-medium text-[#F2F5F9]">
                    {testimonial.author}
                  </div>
                  <div className="text-xs text-[#A7AFBA]">
                    {testimonial.role} · {testimonial.company}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
