import type { ReactNode } from 'react';

interface SectionProps {
  /** Anchor id; also names the heading so the section is a labelled landmark. */
  id: string;
  label: string;
  title: ReactNode;
  aside?: string;
  children: ReactNode;
}

/** The one section shell: spacing, numbered label, title and an optional right-hand note. */
export default function Section({ id, label, title, aside, children }: SectionProps) {
  return (
    <section id={id} className="sec" aria-labelledby={`${id}-title`} data-section={id}>
      <div className="sec-wrap">
        <div className="sec-head">
          <span className="sec-label">{label}</span>
          <h2 id={`${id}-title`} className="sec-title">{title}</h2>
          {aside ? <span className="sec-aside">{aside}</span> : <span />}
        </div>
        {children}
      </div>
    </section>
  );
}
