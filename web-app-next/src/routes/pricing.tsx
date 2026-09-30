import { PLANS } from '../data/pricing';
import { pageMeta } from '../site/meta';

export function meta() {
  return pageMeta({ title: 'Pricing — OpenProxyAI', description: 'Free, Starter, Growth and Enterprise plans for the OpenProxyAI gateway.', path: '/pricing' });
}

export default function PricingRoute() {
  return (
    <main className="mx-auto max-w-page px-4 py-16 sm:px-6 md:py-24">
      <p className="text-step--1 font-medium text-signal">Pricing</p>
      <h1 className="mt-4 text-step-3 font-semibold tracking-tight md:text-step-4">Priced per organisation, not per token.</h1>
      <ul className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {PLANS.map(p => (
          <li key={p.id} className={`flex flex-col rounded-xl border bg-surface p-6 ${p.id === 'growth' ? 'border-signal' : 'border-line'}`}>
            <h2 className="text-step-1 font-semibold">{p.name}</h2>
            <p className="mt-3 font-mono text-step-2">{p.price}</p>
            <p className="mt-1 text-ink-dim">{p.users}<br />{p.retention}</p>
            <ul className="mt-5 space-y-2 text-step--1">
              {p.features.map(f => <li key={f}>— {f}</li>)}
            </ul>
          </li>
        ))}
      </ul>
    </main>
  );
}
