import { useEffect, useRef, useState } from 'react';

function prefersReducedMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export function useCountUp(target: number, durationMs = 900) {
  const ref = useRef<HTMLSpanElement>(null);
  // Starts at the final value so pre-rendered HTML (and crawlers) show the real number.
  const [value, setValue] = useState(target);

  useEffect(() => {
    if (prefersReducedMotion()) return;
    const node = ref.current;
    if (!node) return;
    setValue(0);

    const observer = new IntersectionObserver(
      entries => {
        if (!entries[0].isIntersecting) return;
        observer.disconnect();
        const start = performance.now();
        const tick = (now: number) => {
          const progress = Math.min((now - start) / durationMs, 1);
          const eased = 1 - Math.pow(1 - progress, 3);
          setValue(Math.round(eased * target));
          if (progress < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      },
      { threshold: 0.4 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [target, durationMs]);

  return { ref, value };
}
