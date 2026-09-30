import { useEffect, useRef } from 'react';
import Section from '../../components/Section';

const STEPS = [
  { name: 'Authenticate', header: 'Authorization: Bearer opai_…', body: 'The API key is hashed with SHA-256 and matched; plaintext keys are never stored.' },
  { name: 'Rate limit', header: '429 · 402', body: 'Requests per minute, tokens per minute and dollars per day are checked in Redis before anything is spent.' },
  { name: 'Policy', header: '446', body: 'Model allowlist, blocked keywords, PII redaction and prompt-injection scoring run as hooks.' },
  { name: 'Cache', header: 'X-OpenProxyAI-Cache', body: 'In-memory, then Redis exact match, then pgvector semantic match.' },
  { name: 'Route', header: 'X-OpenProxyAI-Provider', body: 'A weighted, healthy provider key is chosen; tripped circuit breakers are skipped.' },
  { name: 'Upstream', header: 'X-OpenProxyAI-TTFT-Ms', body: 'The call goes out through LiteLLM with fallback on 429 and 5xx.' },
  { name: 'Log', header: 'X-OpenProxyAI-Request-Id', body: 'Cost, tokens and the policy decision are logged asynchronously, never blocking the response.' },
] as const;

export default function FollowRequest() {
  const rootRef = useRef<HTMLOListElement>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    if (!window.matchMedia('(min-width: 1024px)').matches) return;
    let cleanup = () => {};
    let cancelled = false;
    (async () => {
      const [{ gsap }, { ScrollTrigger }] = await Promise.all([import('gsap'), import('gsap/ScrollTrigger')]);
      if (cancelled) return;
      gsap.registerPlugin(ScrollTrigger);
      const ctx = gsap.context(() => {
        root.querySelectorAll<HTMLElement>('[data-step]').forEach(step => {
          gsap.fromTo(step, { opacity: 0.35 }, {
            opacity: 1,
            scrollTrigger: { trigger: step, start: 'top 65%', end: 'bottom 35%', toggleActions: 'play reverse play reverse' },
          });
        });
      }, root);
      cleanup = () => ctx.revert();
    })();
    return () => { cancelled = true; cleanup(); };
  }, []);

  return (
    <Section id="pipeline" eyebrow="Follow one request" title="Seven checks between your app and the model." lede="Every request takes the same path, in the same order.">
      <ol ref={rootRef} className="relative space-y-6 border-l border-line pl-8">
        {STEPS.map((s, i) => (
          <li key={s.name} data-step className="relative">
            <span className="absolute -left-[2.6rem] top-1 flex h-6 w-6 items-center justify-center rounded-full border border-signal bg-bg font-mono text-[11px] text-signal">{i + 1}</span>
            <h3 className="text-step-1 font-semibold">{s.name}</h3>
            <p className="mt-1 font-mono text-step--1 text-signal">{s.header}</p>
            <p className="mt-2 max-w-2xl text-ink-dim">{s.body}</p>
          </li>
        ))}
      </ol>
    </Section>
  );
}
