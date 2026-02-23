import { useRef, useLayoutEffect } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { ArrowRight, Cpu, Layers, Zap } from 'lucide-react';

gsap.registerPlugin(ScrollTrigger);

const providers = [
  { name: 'OpenAI', icon: 'O' },
  { name: 'Anthropic', icon: 'A' },
  { name: 'Gemini', icon: 'G' },
  { name: 'Azure', icon: 'Az' },
  { name: 'Cohere', icon: 'C' },
  { name: 'Mistral', icon: 'M' },
  { name: 'Llama', icon: 'L' },
  { name: 'DeepSeek', icon: 'D' },
  { name: 'Groq', icon: 'Gr' },
];

export default function UnifiedApiSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const leftPanelRef = useRef<HTMLDivElement>(null);
  const rightCardRef = useRef<HTMLDivElement>(null);
  const tilesRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const section = sectionRef.current;
    const leftPanel = leftPanelRef.current;
    const rightCard = rightCardRef.current;
    const tiles = tilesRef.current;

    if (!section || !leftPanel || !rightCard || !tiles) return;

    const tileElements = tiles.querySelectorAll('.provider-tile');
    const lines = section.querySelectorAll('.connection-line');

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
        .fromTo(tileElements, 
          { scale: 0.92, opacity: 0 }, 
          { scale: 1, opacity: 1, stagger: 0.02, ease: 'none' }, 
          0.12
        )
        .fromTo(lines, 
          { strokeDashoffset: 200 }, 
          { strokeDashoffset: 0, ease: 'none' }, 
          0.1
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
    <section ref={sectionRef} className="section-pinned" id="product">
      {/* Background Image */}
      <div className="bg-image absolute inset-0">
        <img
          src="/images/city_overpass_neon.jpg"
          alt="City overpass"
          className="w-full h-full object-cover"
        />
        <div className="bg-overlay" />
      </div>

      {/* Content */}
      <div className="relative z-10 flex items-center min-h-screen px-6 lg:px-[9vw]">
        <div className="w-full flex flex-col lg:flex-row items-center justify-between gap-10 lg:gap-16">
          {/* Left Panel */}
          <div ref={leftPanelRef} className="w-full lg:w-[min(40vw,520px)]">
            <div className="eyebrow-pill text-[#B6FF2E] mb-4">
              Unified API
            </div>
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-[#F2F5F9] mb-4">
              One integration.<br />
              <span className="text-[#B6FF2E]">1600+ models.</span>
            </h2>
            <p className="text-base lg:text-lg text-[#A7AFBA] mb-6">
              Call OpenAI, Anthropic, Gemini, Azure, and open-source models through 
              a single endpoint. Switch providers without changing code.
            </p>
            <ul className="space-y-3 mb-8">
              <li className="flex items-start gap-3">
                <Zap className="w-5 h-5 text-[#B6FF2E] mt-0.5 flex-shrink-0" />
                <code className="text-sm text-[#F2F5F9] mono bg-white/5 px-2 py-1 rounded">
                  provider: "openai"
                </code>
                <span className="text-sm text-[#A7AFBA]">→ instant failover</span>
              </li>
              <li className="flex items-start gap-3">
                <Layers className="w-5 h-5 text-[#B6FF2E] mt-0.5 flex-shrink-0" />
                <code className="text-sm text-[#F2F5F9] mono bg-white/5 px-2 py-1 rounded">
                  provider: "anthropic"
                </code>
                <span className="text-sm text-[#A7AFBA]">→ same request shape</span>
              </li>
              <li className="flex items-start gap-3">
                <Cpu className="w-5 h-5 text-[#B6FF2E] mt-0.5 flex-shrink-0" />
                <span className="text-sm text-[#A7AFBA]">Custom headers / retries / timeouts per call</span>
              </li>
            </ul>
            <a href="#" className="btn-secondary group inline-flex">
              Explore the API
              <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
            </a>
          </div>

          {/* Right Card */}
          <div ref={rightCardRef} className="glass-card w-full lg:w-[min(34vw,420px)] p-6">
            <h3 className="text-lg font-semibold text-[#F2F5F9] mb-4">Supported Providers</h3>
            <div ref={tilesRef} className="relative">
              {/* Connection Lines SVG */}
              <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 0 }}>
                <line className="connection-line" x1="16%" y1="16%" x2="50%" y2="16%" stroke="rgba(182,255,46,0.35)" strokeWidth="1" strokeDasharray="200" strokeDashoffset="0" />
                <line className="connection-line" x1="50%" y1="16%" x2="83%" y2="16%" stroke="rgba(182,255,46,0.35)" strokeWidth="1" strokeDasharray="200" strokeDashoffset="0" />
                <line className="connection-line" x1="16%" y1="16%" x2="16%" y2="50%" stroke="rgba(182,255,46,0.35)" strokeWidth="1" strokeDasharray="200" strokeDashoffset="0" />
                <line className="connection-line" x1="50%" y1="16%" x2="50%" y2="50%" stroke="rgba(182,255,46,0.35)" strokeWidth="1" strokeDasharray="200" strokeDashoffset="0" />
                <line className="connection-line" x1="83%" y1="16%" x2="83%" y2="50%" stroke="rgba(182,255,46,0.35)" strokeWidth="1" strokeDasharray="200" strokeDashoffset="0" />
                <line className="connection-line" x1="16%" y1="50%" x2="50%" y2="50%" stroke="rgba(182,255,46,0.35)" strokeWidth="1" strokeDasharray="200" strokeDashoffset="0" />
                <line className="connection-line" x1="50%" y1="50%" x2="83%" y2="50%" stroke="rgba(182,255,46,0.35)" strokeWidth="1" strokeDasharray="200" strokeDashoffset="0" />
                <line className="connection-line" x1="16%" y1="50%" x2="16%" y2="83%" stroke="rgba(182,255,46,0.35)" strokeWidth="1" strokeDasharray="200" strokeDashoffset="0" />
                <line className="connection-line" x1="50%" y1="50%" x2="50%" y2="83%" stroke="rgba(182,255,46,0.35)" strokeWidth="1" strokeDasharray="200" strokeDashoffset="0" />
                <line className="connection-line" x1="83%" y1="50%" x2="83%" y2="83%" stroke="rgba(182,255,46,0.35)" strokeWidth="1" strokeDasharray="200" strokeDashoffset="0" />
              </svg>
              
              {/* Provider Grid */}
              <div className="grid grid-cols-3 gap-3 relative z-10">
                {providers.map((provider, index) => (
                  <div
                    key={index}
                    className="provider-tile aspect-square rounded-xl bg-white/[0.04] border border-white/10 flex flex-col items-center justify-center gap-2 hover:bg-white/[0.08] hover:border-[#B6FF2E]/30 transition-all cursor-pointer"
                  >
                    <div className="w-10 h-10 rounded-lg bg-[#B6FF2E]/10 flex items-center justify-center text-[#B6FF2E] font-bold text-sm">
                      {provider.icon}
                    </div>
                    <span className="text-xs text-[#A7AFBA]">{provider.name}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="mt-4 text-center">
              <span className="text-xs text-[#A7AFBA]">and 1500+ more...</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
