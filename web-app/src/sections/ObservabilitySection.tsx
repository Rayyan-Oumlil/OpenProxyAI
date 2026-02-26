import { useRef, useLayoutEffect } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { ArrowRight, Filter, Download, Bell } from 'lucide-react';

gsap.registerPlugin(ScrollTrigger);

const logData = [
  { time: '14:32:01', model: 'gpt-4o', tokens: '1,240', cost: '$0.024', status: 'success' },
  { time: '14:31:58', model: 'claude-3', tokens: '892', cost: '$0.018', status: 'success' },
  { time: '14:31:45', model: 'gpt-4o', tokens: '2,100', cost: '$0.042', status: 'cache' },
  { time: '14:31:22', model: 'gemini-pro', tokens: '567', cost: '$0.008', status: 'success' },
  { time: '14:30:59', model: 'gpt-4o-mini', tokens: '3,400', cost: '$0.015', status: 'success' },
];

export default function ObservabilitySection() {
  const sectionRef = useRef<HTMLElement>(null);
  const dashboardRef = useRef<HTMLDivElement>(null);
  const rightPanelRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const section = sectionRef.current;
    const dashboard = dashboardRef.current;
    const rightPanel = rightPanelRef.current;

    if (!section || !dashboard || !rightPanel) return;

    const chartLines = dashboard.querySelectorAll('.chart-line');
    const logRows = dashboard.querySelectorAll('.log-row');

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
        .fromTo(dashboard, 
          { x: '-60vw', opacity: 0 }, 
          { x: 0, opacity: 1, ease: 'none' }, 
          0
        )
        .fromTo(chartLines, 
          { strokeDashoffset: 300 }, 
          { strokeDashoffset: 0, ease: 'none' }, 
          0.1
        )
        .fromTo(logRows, 
          { y: 18, opacity: 0 }, 
          { y: 0, opacity: 1, stagger: 0.02, ease: 'none' }, 
          0.14
        )
        .fromTo(rightPanel, 
          { x: '45vw', opacity: 0 }, 
          { x: 0, opacity: 1, ease: 'none' }, 
          0.08
        );

      // SETTLE (30% - 70%) - hold

      // EXIT (70% - 100%)
      scrollTl
        .fromTo(dashboard, 
          { x: 0, opacity: 1 }, 
          { x: '-18vw', opacity: 0, ease: 'power2.in' }, 
          0.7
        )
        .fromTo(rightPanel, 
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
          src="/images/cyberpunk_street_stores.jpg"
          alt="Cyberpunk street"
          className="w-full h-full object-cover"
        />
        <div className="bg-overlay" />
      </div>

      {/* Content */}
      <div className="relative z-10 flex items-center min-h-screen px-6 lg:px-[9vw]">
        <div className="w-full flex flex-col-reverse lg:flex-row items-center justify-between gap-10 lg:gap-16">
          {/* Left Dashboard */}
          <div ref={dashboardRef} className="glass-card w-full lg:w-[min(44vw,640px)] p-6">
            {/* Window Controls */}
            <div className="flex items-center gap-2 mb-4">
              <div className="w-3 h-3 rounded-full bg-red-500/80" />
              <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
              <div className="w-3 h-3 rounded-full bg-green-500/80" />
              <span className="ml-4 text-sm text-[#A7AFBA]">Live Dashboard</span>
            </div>

            {/* Chart Area */}
            <div className="mb-6">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm text-[#A7AFBA]">Requests & Cost (24h)</span>
                <span className="text-xs text-[#B6FF2E]">+12.5%</span>
              </div>
              <svg viewBox="0 0 400 120" className="w-full h-28">
                {/* Grid lines */}
                <line x1="0" y1="30" x2="400" y2="30" stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
                <line x1="0" y1="60" x2="400" y2="60" stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
                <line x1="0" y1="90" x2="400" y2="90" stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
                
                {/* Cost line (green) */}
                <path
                  className="chart-line"
                  d="M0,80 Q50,75 100,70 T200,55 T300,45 T400,35"
                  fill="none"
                  stroke="#B6FF2E"
                  strokeWidth="2"
                  strokeDasharray="300"
                  strokeDashoffset="0"
                />
                
                {/* Requests line (white) */}
                <path
                  className="chart-line"
                  d="M0,90 Q50,85 100,82 T200,70 T300,60 T400,50"
                  fill="none"
                  stroke="rgba(255,255,255,0.5)"
                  strokeWidth="2"
                  strokeDasharray="300"
                  strokeDashoffset="0"
                />
              </svg>
            </div>

            {/* Log Table */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm text-[#A7AFBA]">Recent Requests</span>
                <span className="text-xs text-[#B6FF2E] bg-[#B6FF2E]/10 px-2 py-1 rounded">Live</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-[#A7AFBA] border-b border-white/10">
                      <th className="pb-2 font-medium">Time</th>
                      <th className="pb-2 font-medium">Model</th>
                      <th className="pb-2 font-medium">Tokens</th>
                      <th className="pb-2 font-medium">Cost</th>
                      <th className="pb-2 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logData.map((row, index) => (
                      <tr key={index} className="log-row border-b border-white/5">
                        <td className="py-2 text-[#F2F5F9] mono text-xs">{row.time}</td>
                        <td className="py-2 text-[#F2F5F9]">{row.model}</td>
                        <td className="py-2 text-[#A7AFBA]">{row.tokens}</td>
                        <td className="py-2 text-[#A7AFBA]">{row.cost}</td>
                        <td className="py-2">
                          {row.status === 'cache' ? (
                            <span className="text-xs bg-[#B6FF2E]/20 text-[#B6FF2E] px-2 py-0.5 rounded">Cache hit</span>
                          ) : (
                            <span className="text-xs bg-green-500/20 text-green-400 px-2 py-0.5 rounded">Success</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Right Panel */}
          <div ref={rightPanelRef} className="w-full lg:w-[min(34vw,420px)]">
            <div className="eyebrow-pill text-[#B6FF2E] mb-4">
              Observability
            </div>
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-[#F2F5F9] mb-4">
              See every request.<br />
              <span className="text-[#B6FF2E]">Control every dollar.</span>
            </h2>
            <p className="text-base lg:text-lg text-[#A7AFBA] mb-6">
              Real-time logs, token usage, and cost attribution across teams, 
              environments, and models.
            </p>
            <ul className="space-y-3 mb-8">
              <li className="flex items-start gap-3">
                <Filter className="w-5 h-5 text-[#B6FF2E] mt-0.5 flex-shrink-0" />
                <span className="text-sm text-[#A7AFBA]">Filter by model, status, user, tag</span>
              </li>
              <li className="flex items-start gap-3">
                <Download className="w-5 h-5 text-[#B6FF2E] mt-0.5 flex-shrink-0" />
                <span className="text-sm text-[#A7AFBA]">Export to S3 / Datadog / webhook</span>
              </li>
              <li className="flex items-start gap-3">
                <Bell className="w-5 h-5 text-[#B6FF2E] mt-0.5 flex-shrink-0" />
                <span className="text-sm text-[#A7AFBA]">Alerts on spend spikes & error rates</span>
              </li>
            </ul>
            <a href="#" className="btn-primary group inline-flex">
              Book a demo
              <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
