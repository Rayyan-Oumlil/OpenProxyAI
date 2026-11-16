import { useEffect } from 'react';
import type { RefObject } from 'react';

const POLICY_STAGE = 2;
const ROUTE_STAGE = 4;
const LOG_STAGE = 5;

/**
 * The page's one signature motion: a request travels the six stages. Every other pass it is stopped
 * at policy (HTTP 446) and still reaches the log. GSAP is loaded on demand and only when the
 * visitor has not asked for reduced motion; otherwise the static legend carries the meaning.
 */
export function usePipelineAnimation(root: RefObject<HTMLElement | null>): void {
  useEffect(() => {
    const container = root.current;
    if (!container) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    let disposed = false;
    let teardown: () => void = () => {};

    void import('gsap').then(({ gsap }) => {
      if (disposed) return;

      const track = container.querySelector<HTMLElement>('.pipe-track');
      const packet = container.querySelector<HTMLElement>('.pipe-packet');
      const nodes = Array.from(container.querySelectorAll<HTMLElement>('.pipe-node'));
      const chips = Array.from(container.querySelectorAll<HTMLElement>('[data-outcome]'));
      if (!track || !packet || nodes.length === 0) return;

      const centerX = (index: number): number => {
        const dot = nodes[index].querySelector<HTMLElement>('.pipe-dot');
        if (!dot) return 0;
        const dotBox = dot.getBoundingClientRect();
        return dotBox.left - track.getBoundingClientRect().left + dotBox.width / 2 - packet.offsetWidth / 2;
      };
      const clear = (): void => {
        nodes.forEach(n => n.classList.remove('is-hot', 'is-blocked'));
        chips.forEach(c => c.classList.remove('is-on'));
        packet.classList.remove('is-bad');
      };

      let timeline: gsap.core.Timeline | null = null;
      let visible = false;
      let running = false;
      let blocked = false;

      const play = (): void => {
        if (disposed || !visible) {
          running = false;
          return;
        }
        running = true;
        const refused = blocked;
        const stops = refused ? [0, 1, POLICY_STAGE] : [0, 1, POLICY_STAGE, 3, ROUTE_STAGE];

        timeline = gsap.timeline({
          onComplete: () => {
            blocked = !blocked;
            play();
          },
        });
        timeline.call(clear).set(packet, { opacity: 1, x: centerX(0) });

        stops.forEach((stage, i) => {
          if (i > 0) timeline!.to(packet, { x: () => centerX(stage), duration: 0.42, ease: 'power2.inOut' });
          timeline!.call(() => nodes[stage].classList.add('is-hot'));
          if (refused && stage === POLICY_STAGE) {
            timeline!.call(() => {
              nodes[stage].classList.remove('is-hot');
              nodes[stage].classList.add('is-blocked');
              packet.classList.add('is-bad');
              chips.find(c => c.dataset.outcome === 'refused')?.classList.add('is-on');
            });
          }
          timeline!.to({}, { duration: 0.18 });
        });

        if (!refused) timeline.call(() => chips.find(c => c.dataset.outcome === 'allowed')?.classList.add('is-on'));
        timeline
          .to(packet, { x: () => centerX(LOG_STAGE), duration: 0.5, ease: 'power2.inOut' }, '+=0.15')
          .call(() => nodes[LOG_STAGE].classList.add('is-hot'))
          .to(packet, { opacity: 0, duration: 0.3 }, '+=0.2')
          .to({}, { duration: 1.1 });
      };

      const observer = new IntersectionObserver(entries => {
        visible = entries[0]?.isIntersecting ?? false;
        if (visible && !running) play();
      }, { threshold: 0.35 });
      observer.observe(container);

      teardown = () => {
        observer.disconnect();
        timeline?.kill();
        clear();
        gsap.set(packet, { clearProps: 'all' });
      };
    });

    return () => {
      disposed = true;
      teardown();
    };
  }, [root]);
}
