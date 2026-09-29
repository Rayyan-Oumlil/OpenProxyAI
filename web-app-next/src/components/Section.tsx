import type { ReactNode } from 'react';

interface SectionProps {
  id?: string;
  eyebrow?: string;
  title: string;
  lede?: string;
  children?: ReactNode;
}

export default function Section({ id, eyebrow, title, lede, children }: SectionProps) {
  return (
    <section id={id} className="mx-auto max-w-page px-4 py-20 sm:px-6 md:py-28">
      {eyebrow && <p className="font-mono text-step--1 uppercase tracking-widest text-signal">{eyebrow}</p>}
      <h2 className="mt-3 max-w-3xl text-step-3 font-semibold leading-tight tracking-tight">{title}</h2>
      {lede && <p className="mt-4 max-w-2xl text-step-1 text-ink-dim">{lede}</p>}
      {children && <div className="mt-12">{children}</div>}
    </section>
  );
}
