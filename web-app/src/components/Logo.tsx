interface LogoMarkProps {
  size?: number;
}

/** The mark: one request comes in, and is routed to the destinations policy allows. */
export function LogoMark({ size = 26 }: LogoMarkProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" role="img" aria-label="OpenProxyAI logo" style={{ flex: 'none' }}>
      <rect width="32" height="32" rx="8" fill="var(--accent)" />
      <g stroke="var(--bg)" strokeWidth="2.4" strokeLinecap="round" fill="none">
        <path d="M6.5 16h7" />
        <path d="M13.5 16 22 9" />
        <path d="M13.5 16 22 23" />
      </g>
      <g fill="var(--bg)">
        <circle cx="13.5" cy="16" r="2.6" />
        <circle cx="24.5" cy="8" r="2" />
        <circle cx="24.5" cy="24" r="2" />
      </g>
    </svg>
  );
}

export default function Logo() {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10, fontWeight: 600, fontSize: 15, letterSpacing: '-0.01em', color: 'var(--ink)' }}>
      <LogoMark />
      <span>OpenProxy<span style={{ color: 'var(--accent)' }}>AI</span></span>
    </span>
  );
}
