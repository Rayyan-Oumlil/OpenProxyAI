import { useEffect } from 'react';

const reducedMotion = (): boolean => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/**
 * The scroll-linked choreography of the home page (progress bar, drawn lines, console frame, marquee).
 * Everything is skipped under prefers-reduced-motion, and the page works without it.
 */
export function useSiteMotion(pathname: string): void {
  useEffect(() => {
    if (reducedMotion()) return;
    let disposed = false;
    let teardown: (() => void) | undefined;

    (async () => {
      const [{ gsap }, { ScrollTrigger }] = await Promise.all([
        import('gsap'), import('gsap/ScrollTrigger'),
      ]);
      if (disposed) return;
      gsap.registerPlugin(ScrollTrigger);
      document.documentElement.classList.add('gs');

      // Native scrolling stays in charge; the marquee speeds up with the scroll speed.
      let speed = 1;
      let lastY = window.scrollY;
      const onScroll = () => {
        const dy = Math.abs(window.scrollY - lastY);
        lastY = window.scrollY;
        speed = 1 + Math.min(dy / 40, 5);
      };
      window.addEventListener('scroll', onScroll, { passive: true });

      const marqs: gsap.core.Tween[] = [];
      const ctx = gsap.context(() => {
        const has = (sel: string) => document.querySelector(sel) !== null;
        if (has('.sprog')) gsap.to('.sprog', { scaleX: 1, ease: 'none', scrollTrigger: { start: 0, end: 'max', scrub: 0.3 } });
        if (has('[data-how="steps"]')) {
          gsap.from('.draw', { scaleX: 0, ease: 'none', stagger: 0.3, scrollTrigger: { trigger: '[data-how="steps"]', start: 'top 82%', end: 'top 38%', scrub: 0.6 } });
          gsap.from('.how-icon', { opacity: 0, scale: 0.6, duration: 0.6, ease: 'back.out(1.8)', stagger: 0.12, scrollTrigger: { trigger: '[data-how="steps"]', start: 'top 80%', once: true } });
        }
        if (has('.shotframe')) {
          gsap.from('.shotframe', { scale: 0.9, y: 70, transformOrigin: '50% 100%', ease: 'none', scrollTrigger: { trigger: '.shotframe', start: 'top 100%', end: 'top 35%', scrub: 0.6 } });
        }
        if (has('[data-marq="fwd"]')) {
          marqs.push(gsap.to('[data-marq="fwd"]', { xPercent: -50, duration: 48, ease: 'none', repeat: -1 }));
          marqs.push(gsap.fromTo('[data-marq="rev"]', { xPercent: -50 }, { xPercent: 0, duration: 62, ease: 'none', repeat: -1 }));
        }
      });

      const tick = () => {
        speed += (1 - speed) * 0.05;
        marqs.forEach(tw => tw.timeScale(tw.timeScale() + (speed - tw.timeScale()) * 0.1));
      };
      gsap.ticker.add(tick);
      gsap.ticker.lagSmoothing(0);
      const refresh = () => ScrollTrigger.refresh();
      document.fonts?.ready.then(refresh);

      teardown = () => {
        window.removeEventListener('scroll', onScroll);
        gsap.ticker.remove(tick);
        ctx.revert();
        document.documentElement.classList.remove('gs');
      };
    })();

    return () => { disposed = true; teardown?.(); };
  }, [pathname]);
}
