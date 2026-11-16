import { CALENDLY_URL, DOCS_URL } from '../lib/links';

export default function FinalCtaSection() {
  return (
    <section className="sec" id="start" aria-labelledby="start-title" data-section="start">
      <div className="sec-wrap">
        <div
          style={{
            padding: '48px 32px', textAlign: 'center',
            border: '1px solid var(--line-2)', borderRadius: 16,
            background: 'linear-gradient(180deg, color-mix(in srgb, var(--accent) 7%, var(--bg)) 0%, var(--bg) 100%)',
          }}
        >
          <h2 id="start-title" className="sec-title" style={{ marginBottom: 12 }}>See it on <em>your own use case.</em></h2>
          <p className="lede" style={{ margin: '0 auto 24px', textAlign: 'center' }}>
            Book a short call. We will show you the console, walk through your rules and answer your security team’s questions.
          </p>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
            <a href={CALENDLY_URL} target="_blank" rel="noopener noreferrer" className="opa-btn opa-btn-primary" data-track="cta_book_demo">Book a demo</a>
            <a href={DOCS_URL} target="_blank" rel="noopener noreferrer" className="opa-btn">Read the documentation</a>
          </div>
        </div>
      </div>
    </section>
  );
}
