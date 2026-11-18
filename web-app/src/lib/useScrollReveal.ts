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

    // A fast jump (anchor link, scrollbar drag) can skip a section without the observer ever seeing it.
    let frame = 0;
    const sweep = () => {
      frame = 0;
      sections.forEach(s => {
        if (!s.classList.contains('in-view') && s.getBoundingClientRect().top < window.innerHeight) {
          s.classList.add('in-view');
          observer.unobserve(s);
        }
      });
    };
    const onScroll = () => { if (!frame) frame = window.requestAnimationFrame(sweep); };
    window.addEventListener('scroll', onScroll, { passive: true });

    return () => {
      observer.disconnect();
      window.removeEventListener('scroll', onScroll);
      if (frame) window.cancelAnimationFrame(frame);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
