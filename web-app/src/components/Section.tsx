import type { ReactNode } from 'react';

interface SectionProps {
  /** Anchor id; also names the heading so the section is a labelled landmark. */
  id: string;
  label: string;
  title: ReactNode;
  aside?: string;
  children: ReactNode;
}

/** The one section shell: a thin-lined rail, a mono eyebrow, a large title and an optional lede on the right. */
export default function Section({ id, label, title, aside, children }: SectionProps) {
  return (
    <section id={id} className="sec" aria-labelledby={`${id}-title`} data-section={id}>
      <div className="sec-wrap">
        <div className="rail sec-rail">
          <div className="sec-head">
            <div style={{ flex: '1.4 1 420px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 20 }}>
              <span className="sec-label">{label}</span>
              <h2 id={`${id}-title`} className="sec-title">{title}</h2>
            </div>
            {aside && <p className="sec-aside">{aside}</p>}
          </div>
          {children}
        </div>
      </div>
    </section>
  );
}
