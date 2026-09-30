import type { Outcome, RequestEvent } from './types';

const OUTCOME_LABEL: Record<Outcome, string> = {
  ok: 'forwarded', cache_hit: 'served from cache', redacted: 'forwarded · redacted',
  blocked_446: 'blocked by guardrail', budget_402: 'budget exceeded', rate_429: 'rate limited',
};

const STATUS_COLOR = { pass: 'text-ok', fail: 'text-danger', skip: 'text-ink-dim' } as const;

export default function TracePanel({ event }: { event: RequestEvent | null }) {
  return (
    <aside aria-live="polite" aria-label="Latest request trace" className="min-h-[21rem] rounded-lg border border-line bg-surface p-4 font-mono text-step--1">
      {event === null ? (
        <p className="text-ink-dim">waiting for traffic…</p>
      ) : (
        <>
          <div className="flex items-baseline justify-between gap-3">
            <span className="truncate text-ink-dim">{event.id}</span>
            <span className={event.statusCode >= 400 ? 'text-danger' : 'text-ok'}>{event.statusCode}</span>
          </div>
          <p className="mt-1 text-ink">{OUTCOME_LABEL[event.outcome]}</p>
          <ol className="mt-3 space-y-1">
            {event.stages.map(s => (
              <li key={s.stage} className="flex justify-between gap-3">
                <span className={STATUS_COLOR[s.status]}>{s.stage}</span>
                <span className="truncate text-right text-ink-dim">{s.detail}</span>
              </li>
            ))}
          </ol>
          <dl className="mt-3 space-y-0.5 border-t border-line pt-3">
            {Object.entries(event.headers).map(([k, v]) => (
              <div key={k} className="flex justify-between gap-3">
                <dt className="truncate text-ink-dim">{k}</dt>
                <dd className="text-ink">{v}</dd>
              </div>
            ))}
          </dl>
        </>
      )}
    </aside>
  );
}
