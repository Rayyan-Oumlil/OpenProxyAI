const STAGES = ['Who is asking?', 'Within limits?', 'Allowed by policy?', 'Already answered?', 'Which approved model?', 'Record everything'];
const SOURCES = ['Employees', 'Applications', 'AI agents'];
const TARGETS: [string, string][] = [['AI models', 'you approve'], ['Your own', 'models'], ['Business', 'tools']];

/** The whole product in one picture: people and apps, one governed layer, only approved destinations. */
export default function HeroDiagram() {
  return (
    <figure className="opa-card" style={{ margin: 0, padding: 14, minWidth: 0 }}>
      <svg viewBox="0 0 640 410" width="100%" role="img" aria-labelledby="hero-diagram-title hero-diagram-desc" style={{ display: 'block' }}>
        <title id="hero-diagram-title">How OpenProxyAI sits between your people and your AI models</title>
        <desc id="hero-diagram-desc">
          Employees, applications and AI agents send requests to OpenProxyAI. For each one it checks who is asking, whether they are within limits, whether policy allows it, whether it was already answered,
          which approved model to use, and it records everything. Allowed requests reach approved AI models, your own models or business tools. A request that policy refuses is stopped with a clear reason and still recorded.
        </desc>
        <defs>
          <marker id="hd-arrow" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 Z" fill="var(--accent)" /></marker>
          <marker id="hd-arrow-bad" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 Z" fill="var(--err)" /></marker>
        </defs>

        <text x="14" y="24" fontFamily="var(--sans)" fontSize="12" fontWeight="600" letterSpacing="1.2" fill="var(--ink-3)">YOUR PEOPLE AND APPS</text>
        <text x="236" y="24" fontFamily="var(--sans)" fontSize="12" fontWeight="600" letterSpacing="1.2" fill="var(--accent)">OPENPROXYAI</text>
        <text x="494" y="24" fontFamily="var(--sans)" fontSize="12" fontWeight="600" letterSpacing="1.2" fill="var(--ink-3)">APPROVED ONLY</text>

        {SOURCES.map((name, i) => (
          <g key={name}>
            <rect x="14" y={50 + i * 82} width="120" height="54" rx="10" fill="var(--panel-2)" stroke="var(--line-2)" />
            <text x="74" y={82 + i * 82} textAnchor="middle" fontFamily="var(--sans)" fontSize="14.5" fontWeight="500" fill="var(--ink)">{name}</text>
            <line x1="134" y1={77 + i * 82} x2="230" y2="190" stroke="var(--accent)" strokeWidth="1.5" markerEnd="url(#hd-arrow)" opacity="0.75" />
          </g>
        ))}

        <rect x="234" y="36" width="196" height="276" rx="14" fill="var(--bg-2)" stroke="var(--accent)" strokeWidth="1.8" />
        {STAGES.map((stage, i) => (
          <g key={stage}>
            <rect x="248" y={52 + i * 42} width="168" height="34" rx="8" fill={i === 2 ? 'color-mix(in srgb, var(--accent) 14%, var(--panel))' : 'var(--panel)'} stroke={i === 2 ? 'var(--accent)' : 'var(--line-2)'} />
            <text x="332" y={74 + i * 42} textAnchor="middle" fontFamily="var(--sans)" fontSize="13" fontWeight="500" fill="var(--ink)">{stage}</text>
          </g>
        ))}

        {TARGETS.map(([line1, line2], i) => (
          <g key={line1}>
            <line x1="430" y1="174" x2="500" y2={77 + i * 82} stroke="var(--accent)" strokeWidth="1.5" markerEnd="url(#hd-arrow)" opacity="0.75" />
            <rect x="504" y={50 + i * 82} width="124" height="54" rx="10" fill="var(--panel-2)" stroke="var(--line-2)" />
            <text x="566" y={73 + i * 82} textAnchor="middle" fontFamily="var(--sans)" fontSize="13.5" fontWeight="500" fill="var(--ink)">{line1}</text>
            <text x="566" y={90 + i * 82} textAnchor="middle" fontFamily="var(--sans)" fontSize="12.5" fill="var(--ink-3)">{line2}</text>
          </g>
        ))}

        <path d="M332 312 V346" stroke="var(--err)" strokeWidth="1.6" strokeDasharray="4 4" markerEnd="url(#hd-arrow-bad)" />
        <rect x="190" y="350" width="284" height="48" rx="10" fill="color-mix(in srgb, var(--err) 8%, var(--panel))" stroke="var(--err)" />
        <text x="332" y="371" textAnchor="middle" fontFamily="var(--sans)" fontSize="13.5" fontWeight="600" fill="var(--err)">Not allowed: stopped, with a reason</text>
        <text x="332" y="388" textAnchor="middle" fontFamily="var(--sans)" fontSize="12.5" fill="var(--ink-3)">and still on the record</text>
      </svg>
    </figure>
  );
}
