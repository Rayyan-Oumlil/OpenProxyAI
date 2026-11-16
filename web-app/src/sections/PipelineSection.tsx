import { useRef } from 'react';
import Section from '../components/Section';
import { usePipelineAnimation } from '../lib/usePipelineAnimation';

const STAGES = [
  { t: 'Who is asking?', d: 'identify the person or app' },
  { t: 'Within limits?', d: 'usage and budget' },
  { t: 'Allowed by policy?', d: 'your rules' },
  { t: 'Already answered?', d: 'reuse saves cost' },
  { t: 'Which model?', d: 'approved, by sensitivity' },
  { t: 'Record it', d: 'always, after the answer' },
];

const WHY = [
  { title: 'Cheap checks first', text: 'Identity and limits come first, so a request that will be refused anyway costs almost nothing.' },
  { title: 'Rules before shortcuts', text: 'Your policy is applied before any saved answer is reused, so a refused request can never be answered from memory.' },
  { title: 'The record never slows anyone', text: 'Recording happens after the answer is sent. Refused requests are recorded too.' },
];

export default function PipelineSection() {
  const rootRef = useRef<HTMLDivElement>(null);
  usePipelineAnimation(rootRef);

  return (
    <Section id="pipeline" label="How it works" title={<>Every request goes through the same <em>six checks.</em></>} aside="in this order, every time">
      <div ref={rootRef}>
        <div className="pipe-track" role="list" aria-label="Checks applied to every request, in order" style={{ marginBottom: 8 }}>
          <div aria-hidden="true" style={{ position: 'absolute', left: 15, right: 15, top: 15, height: 1, background: 'var(--line-2)' }} />
          <span className="pipe-packet" aria-hidden="true" />
          {STAGES.map((s, i) => (
            <div key={s.t} className="pipe-node" role="listitem">
              <span className="pipe-dot">{i + 1}</span>
              <span style={{ color: 'var(--ink)', fontSize: 14, fontWeight: 500 }}>{s.t}</span>
              <span style={{ color: 'var(--ink-3)', fontSize: 12.5 }}>{s.d}</span>
            </div>
          ))}
        </div>
        <div className="pipe-outcome" aria-label="Possible outcomes">
          <span data-outcome="allowed">Allowed: sent to an approved model, then recorded</span>
          <span data-outcome="refused" className="bad">Not allowed: stopped with a clear reason, still recorded</span>
        </div>
      </div>

      <div className="grid-3" style={{ marginTop: 40 }}>
        {WHY.map(w => (
          <div key={w.title} className="opa-card" style={{ padding: 22 }}>
            <h3 style={{ margin: '0 0 6px', color: 'var(--ink)', fontSize: 16, fontWeight: 600 }}>{w.title}</h3>
            <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 14.5, lineHeight: 1.6, color: 'var(--ink-2)' }}>{w.text}</p>
          </div>
        ))}
      </div>
      <p className="note">
        The checks add a small amount of time to each request. We publish no speed figure yet because we do not have a benchmark anyone can reproduce. The demo shows the time taken by each check on your own hardware.
      </p>
    </Section>
  );
}
