import { useEffect } from 'react';
import { trackEvent } from './analytics';

/**
 * Two signals, both anonymous and cookie-free:
 *  - clicks on any element carrying data-track="<event name>" (CTAs, plan buttons);
 *  - the first time each section with a data-section id is at least 40% visible on a page.
 * Together they show which call to action is used and how far down a page people read.
 */
export function useSiteMeasurement(pathname: string): void {
  useEffect(() => {
    const onClick = (event: MouseEvent): void => {
      const target = event.target instanceof Element ? event.target.closest<HTMLElement>('[data-track]') : null;
      const name = target?.dataset.track;
      if (name) trackEvent(name, { page: pathname });
    };
    document.addEventListener('click', onClick);
    return () => document.removeEventListener('click', onClick);
  }, [pathname]);

  useEffect(() => {
    const sections = document.querySelectorAll<HTMLElement>('main [data-section]');
    if (sections.length === 0) return;

    const observer = new IntersectionObserver(
      entries => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const id = (entry.target as HTMLElement).dataset.section;
          if (id) trackEvent('section_view', { page: pathname, section: id });
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.4 },
    );
    sections.forEach(section => observer.observe(section));
    return () => observer.disconnect();
  }, [pathname]);
}
