import type { ReactNode } from 'react';
import { CALENDLY_URL } from '../lib/links';

interface PageHeaderProps {
  eyebrow: string;
  title: ReactNode;
  description: string;
  /** Optional second button: where to jump on the page. */
  secondary?: { label: string; href: string };
  visual?: ReactNode;
}

/** The first screen of every inner page: eyebrow, large quiet title, lede, and one framed visual on a pale blue-grey block. */
export default function PageHeader({ eyebrow, title, description, secondary, visual }: PageHeaderProps) {
  return (
    <section style={{ position: 'relative', padding: '0 24px', marginTop: -70 }} aria-label={eyebrow}>
      <div className="dots" aria-hidden="true" style={{ position: 'absolute', top: 0, right: 0, width: '66%', height: 560, backgroundImage: 'radial-gradient(#c9d2d8 1px, transparent 1.4px)', backgroundSize: '22px 22px', WebkitMaskImage: 'radial-gradient(ellipse at 70% 30%, #000 0%, transparent 68%)', maskImage: 'radial-gradient(ellipse at 70% 30%, #000 0%, transparent 68%)', pointerEvents: 'none' }} />
      <div className="rail" style={{ maxWidth: 1240, margin: '0 auto', padding: '176px clamp(20px, 4vw, 56px) 96px', display: 'flex', flexDirection: 'column', gap: 64 }}>
        <div style={{ position: 'relative', display: 'flex', flexWrap: 'wrap', gap: '40px 72px', alignItems: 'flex-end' }}>
          <div style={{ flex: '1.5 1 520px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 28 }}>
            <p className="eyebrow rise">{eyebrow}</p>
            <h1 style={{ margin: 0, fontSize: 'clamp(40px, 5.4vw, 72px)', lineHeight: 1.03, fontWeight: 500, letterSpacing: '-0.038em', textWrap: 'balance' }}>{title}</h1>
          </div>
          <div className="rise" style={{ flex: '1 1 360px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 28, animationDelay: '.6s' }}>
            <p style={{ margin: 0, fontSize: 18, lineHeight: 1.6, color: 'var(--ink-2)', textWrap: 'pretty' }}>{description}</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
              <a className="btn-p" href={CALENDLY_URL} target="_blank" rel="noopener noreferrer" data-track="cta_book_demo" style={{ fontSize: 16, padding: '0 24px', minHeight: 48 }}>Book a demo</a>
              {secondary && <a className="btn-s" href={secondary.href} style={{ fontSize: 16, padding: '0 24px', minHeight: 48 }}>{secondary.label}</a>}
            </div>
          </div>
        </div>
        {visual && (
          <div className="rise" style={{ position: 'relative', borderRadius: 28, padding: 'clamp(10px, 3.2vw, 44px)', background: 'var(--sky)', overflow: 'hidden', animationDelay: '.8s' }}>
            <div className="blob" aria-hidden="true" style={{ position: 'absolute', top: -180, left: -80, width: 520, height: 520, borderRadius: 999, background: '#f7f5f0', filter: 'blur(80px)', opacity: 0.9 }} />
            <div className="dots" aria-hidden="true" style={{ position: 'absolute', inset: 0, backgroundImage: 'radial-gradient(#aebfc9 1px, transparent 1.4px)', backgroundSize: '22px 22px', opacity: 0.55, WebkitMaskImage: 'linear-gradient(180deg, #000, transparent 55%)', maskImage: 'linear-gradient(180deg, #000, transparent 55%)' }} />
            <div style={{ position: 'relative' }}>{visual}</div>
          </div>
        )}
      </div>
    </section>
  );
}
