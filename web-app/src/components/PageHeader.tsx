import type { ReactNode } from 'react';
import { PAGE_MAX_WIDTH } from '../lib/layout';

interface PageHeaderProps {
  eyebrow: string;
  title: ReactNode;
  description: string;
  cta?: ReactNode;
}

export default function PageHeader({ eyebrow, title, description, cta }: PageHeaderProps) {
  return (
    <div style={{ borderBottom: '1px solid var(--line)' }}>
      <div style={{ maxWidth: PAGE_MAX_WIDTH, margin: '0 auto', padding: '48px 24px 40px' }}>
        <span style={{ fontSize: 11, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.2em' }}>{eyebrow}</span>
        <h1 style={{ fontFamily: 'var(--sans)', fontSize: 'clamp(30px,3.4vw,46px)', lineHeight: 1.08, letterSpacing: '-0.03em', fontWeight: 500, margin: '12px 0 0', color: 'var(--ink)', maxWidth: '20ch' }}>
          {title}
        </h1>
        <p style={{ fontFamily: 'var(--sans)', fontSize: 15, lineHeight: 1.6, color: 'var(--ink-2)', margin: '14px 0 0', maxWidth: '60ch' }}>
          {description}
        </p>
        {cta && <div style={{ display: 'flex', gap: 8, marginTop: 20 }}>{cta}</div>}
      </div>
    </div>
  );
}
