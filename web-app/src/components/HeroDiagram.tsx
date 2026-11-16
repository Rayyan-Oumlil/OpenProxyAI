const STAGES = ['auth', 'rate limit', 'policy', 'cache', 'route', 'log'];
const CALLERS = ['Apps', 'Agents', 'Scripts'];
const TARGETS: [string, string][] = [['Hosted', 'providers'], ['Your own', 'endpoints'], ['MCP tool', 'servers']];

/** The whole product in one picture: callers, one governed gateway, only approved destinations. */
export default function HeroDiagram() {
  return (
    <figure className="opa-card" style={{ margin: 0, padding: 14, minWidth: 0 }}>
      <svg viewBox="0 0 620 400" width="100%" role="img" aria-labelledby="hero-diagram-title hero-diagram-desc" style={{ display: 'block' }}>
        <title id="hero-diagram-title">How OpenProxyAI sits between your callers and your models</title>
        <desc id="hero-diagram-desc">
          Apps, agents and scripts send requests to OpenProxyAI. It runs six stages: auth, rate limit, policy, cache, route and log.
          Approved requests go to hosted providers, your own endpoints or MCP tool servers. A request that policy refuses is answered with HTTP 446 and still logged.
        </desc>
        <defs>
          <marker id="hd-arrow" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 Z" fill="var(--accent)" /></marker>
          <marker id="hd-arrow-bad" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 Z" fill="var(--err)" /></marker>
        </defs>

        <text x="20" y="22" fontFamily="var(--mono)" fontSize="11" letterSpacing="2" fill="var(--ink-3)">CALLERS</text>
        <text x="228" y="22" fontFamily="var(--mono)" fontSize="11" letterSpacing="2" fill="var(--accent)">YOUR ENVIRONMENT</text>
        <text x="500" y="22" fontFamily="var(--mono)" fontSize="11" letterSpacing="2" fill="var(--ink-3)">APPROVED ONLY</text>

        {CALLERS.map((name, i) => (
          <g key={name}>
            <rect x="14" y={58 + i * 78} width="112" height="52" rx="8" fill="var(--panel-2)" stroke="var(--line-2)" />
            <text x="70" y={89 + i * 78} textAnchor="middle" fontFamily="var(--mono)" fontSize="14" fill="var(--ink)">{name}</text>
            <line x1="126" y1={84 + i * 78} x2="222" y2="196" stroke="var(--accent)" strokeWidth="1.4" markerEnd="url(#hd-arrow)" opacity="0.8" />
          </g>
        ))}

        <rect x="226" y="40" width="190" height="256" rx="12" fill="var(--panel)" stroke="var(--accent)" strokeWidth="1.6" />
        <text x="321" y="66" textAnchor="middle" fontFamily="var(--sans)" fontSize="16" fontWeight="500" fill="var(--ink)">OpenProxyAI</text>
        {STAGES.map((stage, i) => (
          <g key={stage}>
            <rect x="244" y={80 + i * 33} width="154" height="26" rx="6" fill={stage === 'policy' ? 'color-mix(in srgb, var(--accent) 16%, var(--panel-2))' : 'var(--panel-2)'} stroke={stage === 'policy' ? 'var(--accent)' : 'var(--line)'} />
            <text x="258" y={98 + i * 33} fontFamily="var(--mono)" fontSize="12" fill="var(--ink-3)">{i + 1}</text>
            <text x="278" y={98 + i * 33} fontFamily="var(--mono)" fontSize="13" fill="var(--ink)">{stage}</text>
          </g>
        ))}

        {TARGETS.map(([line1, line2], i) => (
          <g key={line1}>
            <line x1="416" y1="150" x2="490" y2={84 + i * 78} stroke="var(--accent)" strokeWidth="1.4" markerEnd="url(#hd-arrow)" opacity="0.8" />
            <rect x="494" y={58 + i * 78} width="112" height="52" rx="8" fill="var(--panel-2)" stroke="var(--line-2)" />
            <text x="550" y={80 + i * 78} textAnchor="middle" fontFamily="var(--mono)" fontSize="12" fill="var(--ink)">{line1}</text>
            <text x="550" y={96 + i * 78} textAnchor="middle" fontFamily="var(--mono)" fontSize="12" fill="var(--ink-3)">{line2}</text>
          </g>
        ))}

        <path d="M321 296 V334" stroke="var(--err)" strokeWidth="1.4" strokeDasharray="4 4" markerEnd="url(#hd-arrow-bad)" />
        <rect x="176" y="338" width="290" height="46" rx="8" fill="color-mix(in srgb, var(--err) 12%, var(--panel))" stroke="var(--err)" />
        <text x="321" y="357" textAnchor="middle" fontFamily="var(--mono)" fontSize="13" fill="var(--err)">refused: HTTP 446</text>
        <text x="321" y="373" textAnchor="middle" fontFamily="var(--mono)" fontSize="11.5" fill="var(--ink-3)">plain-language reason, still logged</text>
      </svg>
      <figcaption className="note" style={{ margin: '8px 4px 0' }}>Data class decides which destinations a request may reach. Postgres and Redis run beside the gateway.</figcaption>
    </figure>
  );
}
