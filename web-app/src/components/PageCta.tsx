import { CALENDLY_URL } from '../lib/links';

interface PageCtaProps { title: string; body: string }

/** The closing band of every inner page. */
export default function PageCta({ title, body }: PageCtaProps) {
  return (
    <section id="contact" aria-labelledby="contact-title" data-section="contact" style={{ padding: '0 24px 24px', borderTop: '1px solid var(--line)', scrollMarginTop: 110 }}>
      <div className="rail" style={{ maxWidth: 1240, margin: '0 auto', padding: '24px clamp(10px, 2vw, 24px)' }}>
        <div style={{ position: 'relative', borderRadius: 28, padding: 'clamp(40px, 7vw, 104px) clamp(24px, 5vw, 72px)', background: 'var(--sky)', overflow: 'hidden' }}>
          <div className="blob" aria-hidden="true" style={{ position: 'absolute', top: -200, right: -60, width: 560, height: 560, borderRadius: 999, background: '#f7f5f0', filter: 'blur(80px)', opacity: 0.9 }} />
          <div className="dots" aria-hidden="true" style={{ position: 'absolute', inset: 0, backgroundImage: 'radial-gradient(#aebfc9 1px, transparent 1.4px)', backgroundSize: '22px 22px', opacity: 0.6, WebkitMaskImage: 'radial-gradient(ellipse at 85% 50%, #000 0%, transparent 60%)', maskImage: 'radial-gradient(ellipse at 85% 50%, #000 0%, transparent 60%)', pointerEvents: 'none' }} />
          <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', gap: 32, alignItems: 'flex-start' }}>
            <h2 id="contact-title" style={{ margin: 0, maxWidth: 860, fontSize: 'clamp(34px, 4.4vw, 60px)', lineHeight: 1.04, fontWeight: 500, letterSpacing: '-0.035em', textWrap: 'balance' }}>{title}</h2>
            <p style={{ margin: 0, maxWidth: 620, fontSize: 18, color: 'var(--ink-2)', textWrap: 'pretty' }}>{body}</p>
            <a className="btn-p" href={CALENDLY_URL} target="_blank" rel="noopener noreferrer" data-track="cta_book_demo" style={{ fontSize: 16, padding: '0 24px', minHeight: 48 }}>Book a demo</a>
          </div>
        </div>
      </div>
    </section>
  );
}
