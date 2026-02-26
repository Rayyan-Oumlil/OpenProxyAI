import { useRef, useLayoutEffect } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { ArrowRight, Github, Twitter, Linkedin, MessageCircle } from 'lucide-react';

gsap.registerPlugin(ScrollTrigger);

const footerLinks = {
  Product: ['Gateway', 'Observability', 'Guardrails', 'Pricing'],
  Docs: ['Quickstart', 'API Reference', 'SDKs', 'Status'],
  Trust: ['Security', 'Compliance', 'SOC 2', 'Privacy'],
  Company: ['Blog', 'Contact', 'Legal'],
};

export default function FooterSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const ctaRef = useRef<HTMLDivElement>(null);
  const footerRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const section = sectionRef.current;
    const cta = ctaRef.current;
    const footer = footerRef.current;

    if (!section || !cta || !footer) return;

    const ctx = gsap.context(() => {
      // CTA animation
      gsap.fromTo(cta,
        { y: 18, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          duration: 0.6,
          scrollTrigger: {
            trigger: cta,
            start: 'top 80%',
            end: 'top 60%',
            scrub: true,
          }
        }
      );

      // Footer columns animation
      const columns = footer.querySelectorAll('.footer-column');
      gsap.fromTo(columns,
        { y: 20, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          stagger: 0.08,
          duration: 0.5,
          scrollTrigger: {
            trigger: footer,
            start: 'top 85%',
            end: 'top 65%',
            scrub: true,
          }
        }
      );
    }, section);

    return () => ctx.revert();
  }, []);

  return (
    <section ref={sectionRef} className="relative">
      {/* Background Image */}
      <div className="bg-image absolute inset-0">
        <img
          src="/images/tunnel_neon_rings.jpg"
          alt="Neon tunnel"
          className="w-full h-full object-cover"
        />
        <div className="bg-overlay" />
      </div>

      {/* CTA Section */}
      <div ref={ctaRef} className="relative z-10 pt-20 lg:pt-28 pb-16 px-6">
        <div className="max-w-[920px] mx-auto text-center">
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-[#F2F5F9] mb-4">
            Ready to simplify your <span className="text-[#B6FF2E]">AI stack?</span>
          </h2>
          <p className="text-base lg:text-lg text-[#A7AFBA] mb-8 max-w-[50ch] mx-auto">
            Get started in minutes. No credit card required.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <a href="#" className="btn-primary group">
              Get started free
              <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
            </a>
            <a href="#" className="btn-secondary">
              Talk to sales
            </a>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer ref={footerRef} className="relative z-10 border-t border-white/10 bg-[#0B0C0F]/80 backdrop-blur-sm">
        <div className="px-6 lg:px-[9vw] py-12 lg:py-16">
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-8 lg:gap-12">
            {/* Logo & Tagline */}
            <div className="col-span-2 md:col-span-4 lg:col-span-2 footer-column">
              <a href="#" className="inline-block mb-4">
                <span className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
                  openproxy<span className="text-[#B6FF2E]">AI</span>
                </span>
              </a>
              <p className="text-sm text-[#A7AFBA] mb-6 max-w-[30ch]">
                One API. Every Model. Total Control.
              </p>
              <div className="flex items-center gap-4">
                <a href="#" className="text-[#A7AFBA] hover:text-[#B6FF2E] transition-colors">
                  <Twitter className="w-5 h-5" />
                </a>
                <a href="#" className="text-[#A7AFBA] hover:text-[#B6FF2E] transition-colors">
                  <Linkedin className="w-5 h-5" />
                </a>
                <a href="#" className="text-[#A7AFBA] hover:text-[#B6FF2E] transition-colors">
                  <Github className="w-5 h-5" />
                </a>
                <a href="#" className="text-[#A7AFBA] hover:text-[#B6FF2E] transition-colors">
                  <MessageCircle className="w-5 h-5" />
                </a>
              </div>
            </div>

            {/* Links */}
            {Object.entries(footerLinks).map(([category, links], index) => (
              <div key={index} className="footer-column">
                <h4 className="text-sm font-semibold text-[#F2F5F9] mb-4">
                  {category}
                </h4>
                <ul className="space-y-3">
                  {links.map((link, linkIndex) => (
                    <li key={linkIndex}>
                      <a
                        href="#"
                        className="text-sm text-[#A7AFBA] hover:text-[#F2F5F9] transition-colors"
                      >
                        {link}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          {/* Bottom Bar */}
          <div className="mt-12 pt-8 border-t border-white/10 flex flex-col sm:flex-row items-center justify-between gap-4">
            <p className="text-xs text-[#A7AFBA]">
              © 2026 openproxyAI. All rights reserved.
            </p>
            <div className="flex items-center gap-6">
              <a href="#" className="text-xs text-[#A7AFBA] hover:text-[#F2F5F9] transition-colors">
                Privacy
              </a>
              <a href="#" className="text-xs text-[#A7AFBA] hover:text-[#F2F5F9] transition-colors">
                Terms
              </a>
              <a href="#" className="text-xs text-[#A7AFBA] hover:text-[#F2F5F9] transition-colors">
                Cookies
              </a>
            </div>
          </div>
        </div>
      </footer>
    </section>
  );
}
