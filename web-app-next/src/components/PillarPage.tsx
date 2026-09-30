import { useState, type ReactNode } from 'react';
import { capabilitiesFor, type Pillar } from '../data/capabilities';
import ControlMap from '../map/ControlMap';
import TracePanel from '../map/TracePanel';
import { SCENES, type SceneId } from '../map/scenes';
import type { RequestEvent } from '../map/types';
import FeatureGrid from './FeatureGrid';
import Section from './Section';

interface PillarPageProps {
  pillar: Pillar;
  sceneId: SceneId;
  eyebrow: string;
  title: string;
  lede: string;
  children?: ReactNode;
}

export default function PillarPage({ pillar, sceneId, eyebrow, title, lede, children }: PillarPageProps) {
  const [last, setLast] = useState<RequestEvent | null>(null);
  return (
    <main>
      <section className="relative overflow-hidden">
        <div className="grid-bg pointer-events-none absolute inset-0" aria-hidden />
        <div className="relative mx-auto max-w-page px-4 pb-12 pt-16 sm:px-6 md:pt-24">
          <p className="text-step--1 font-medium text-signal">{eyebrow}</p>
          <h1 className="mt-4 max-w-3xl text-step-3 font-semibold leading-tight tracking-tight md:text-step-4">{title}</h1>
          <p className="mt-5 max-w-2xl text-step-1 text-ink-dim">{lede}</p>
          <div className="mt-12 grid gap-4 lg:grid-cols-[1fr_20rem]">
            <ControlMap scene={SCENES[sceneId]} onEvent={setLast} className="rounded-xl border border-line bg-surface/60 p-2" />
            <TracePanel event={last} />
          </div>
        </div>
      </section>
      <Section title={`What ${eyebrow.toLowerCase()} covers`}>
        <FeatureGrid items={capabilitiesFor(pillar)} />
      </Section>
      {children}
    </main>
  );
}
