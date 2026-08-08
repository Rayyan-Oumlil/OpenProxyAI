import { useEffect } from 'react';

export function useScrollReveal(deps: readonly unknown[]): void {
  useEffect(() => {
    const sections = document.querySelectorAll<HTMLElement>('main section');
    if (sections.length === 0) return;

    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReduced) {
      sections.forEach(s => s.classList.add('reveal', 'in-view'));
      return;
    }

    const observer = new IntersectionObserver(
      entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('in-view');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -60px 0px' },
    );

    sections.forEach(s => {
      s.classList.add('reveal');
      observer.observe(s);
    });

    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
