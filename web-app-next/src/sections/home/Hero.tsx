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
      <div className="relative mx-auto max-w-page px-4 pb-16 pt-10 sm:px-6 md:pt-14">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-end">
          <h1 className="max-w-4xl text-step-3 font-semibold leading-[1.05] tracking-tight lg:text-[3.25rem]">
            The control plane for enterprise AI — every model call and every agent action, governed and audited.
          </h1>
          <div>
            <p className="text-ink-dim">
              One gateway between your organisation and every model provider and tool server, in your cloud or fully air-gapped.
            </p>
            <div className="mt-5 flex flex-wrap gap-3">
              <a href={DOCS_URL} className="rounded-md bg-signal px-4 py-2 font-semibold text-bg hover:brightness-110">Read the docs</a>
              <Link to="/engineering" className="rounded-md border border-line px-4 py-2 text-ink hover:border-ink-dim">How it's built</Link>
            </div>
          </div>
        </div>
        <div className="mt-10 grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <ControlMap scene={SCENES.home} onEvent={setLast} className="rounded-xl border border-line bg-surface/60 p-2" />
          <TracePanel event={last} />
        </div>
      </div>
    </section>
  );
}
