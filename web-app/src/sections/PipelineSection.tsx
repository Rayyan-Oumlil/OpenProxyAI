import { useRef } from 'react';
import Section from '../components/Section';
import { usePipelineAnimation } from '../lib/usePipelineAnimation';
import { docsPage } from '../lib/links';

const STAGES = [
  { t: 'auth', d: 'api key' },
  { t: 'rate limit', d: 'rpm · tpm · budget' },
  { t: 'policy', d: 'allow · block · log' },
  { t: 'cache', d: 'L1 · L2 · L3' },
  { t: 'route', d: 'approved model + key' },
  { t: 'log', d: 'async, after the reply' },
];

const WHY = [
  { title: 'Cheap rejections first', text: 'Auth and rate limits run before anything else, so a request you will refuse anyway costs almost nothing.' },
  { title: 'Policy before the cache', text: 'A cache check first could answer a request your policy would block, from an entry stored before the rule existed. Policy first means a refused request never reaches the cache or a provider.' },
  { title: 'Logging never blocks', text: 'The log is written after the response has gone back, so a slow log backend is never the reason your request is slow. Refused requests are logged too.' },
];

export default function PipelineSection() {
  const rootRef = useRef<HTMLDivElement>(null);
  usePipelineAnimation(rootRef);

  return (
    <Section id="pipeline" label="§05 · how a request flows" title={<>Six stages, in an order <em>that matters.</em></>} aside="policy runs before cache">
      <div ref={rootRef}>
        <div className="pipe-track" role="list" aria-label="Request stages, in order" style={{ marginBottom: 8 }}>
          <div aria-hidden="true" style={{ position: 'absolute', left: 15, right: 15, top: 15, height: 1, background: 'var(--line-2)' }} />
          <span className="pipe-packet" aria-hidden="true" />
          {STAGES.map((s, i) => (
            <div key={s.t} className="pipe-node" role="listitem">
              <span className="pipe-dot">{i + 1}</span>
              <span style={{ color: 'var(--ink)', fontSize: 12.5 }}>{s.t}</span>
              <span style={{ color: 'var(--ink-3)', fontSize: 10.5 }}>{s.d}</span>
            </div>
          ))}
        </div>
        <div className="pipe-outcome" aria-label="Possible outcomes">
          <span data-outcome="allowed">allowed → provider, then logged</span>
          <span data-outcome="refused" className="bad">refused → 446 with an explanation, still logged</span>
        </div>
      </div>

      <div className="grid-3" style={{ marginTop: 40 }}>
        {WHY.map(w => (
          <div key={w.title} className="opa-card" style={{ padding: 20 }}>
            <div style={{ color: 'var(--ink)', fontSize: 13.5, fontWeight: 500, marginBottom: 6 }}>{w.title}</div>
            <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 13.5, lineHeight: 1.6, color: 'var(--ink-2)' }}>{w.text}</p>
          </div>
        ))}
      </div>
      <p className="note">
        We publish no latency figure for these stages: there is no reproducible benchmark yet. When there is, it will appear here with its method and hardware.{' '}
        <a href={docsPage('/core-concepts/request-pipeline')} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>Request pipeline docs →</a>
      </p>
    </Section>
  );
}
