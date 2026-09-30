import { useState } from 'react';
import { Link } from 'react-router';
import ControlMap from '../../map/ControlMap';
import TracePanel from '../../map/TracePanel';
import { SCENES } from '../../map/scenes';
import type { RequestEvent } from '../../map/types';
import { DOCS_URL } from '../../site/links';

export default function Hero() {
  const [last, setLast] = useState<RequestEvent | null>(null);
  return (
    <section className="relative overflow-hidden">
      <div className="grid-bg pointer-events-none absolute inset-0" aria-hidden />
      <div className="relative mx-auto max-w-page px-4 pb-16 pt-16 sm:px-6 md:pt-24">
        <p className="font-mono text-step--1 uppercase tracking-widest text-signal">AI control plane</p>
        <h1 className="mt-4 max-w-4xl text-step-3 font-semibold leading-[1.05] tracking-tight md:text-step-4">
          The control plane for enterprise AI — every model call and every agent action, governed and audited.
        </h1>
        <p className="mt-6 max-w-2xl text-step-1 text-ink-dim">
          One gateway between your organisation and every model provider and tool server. Policies, budgets, routing and a complete audit trail — in your cloud or fully air-gapped.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <a href={DOCS_URL} className="rounded-md bg-signal px-4 py-2 font-semibold text-bg hover:brightness-110">Read the docs</a>
          <Link to="/engineering" className="rounded-md border border-line px-4 py-2 text-ink hover:border-ink-dim">How it's built</Link>
        </div>
        <div className="mt-14 grid gap-4 lg:grid-cols-[1fr_20rem]">
          <ControlMap scene={SCENES.home} onEvent={setLast} className="rounded-xl border border-line bg-surface/60 p-2" />
          <TracePanel event={last} />
        </div>
      </div>
    </section>
  );
}
