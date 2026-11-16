import { useState } from 'react';
import Section from '../components/Section';

interface Shot {
  id: string;
  tab: string;
  title: string;
  text: string;
  alt: string;
}

const SHOTS: Shot[] = [
  {
    id: 'trace',
    tab: 'Request detail',
    title: 'Open any request and see exactly what happened.',
    text: 'The decision, the sensitivity of the data (here: confidential, a social security number was detected), the message the user received, and proof that nothing was sent to an AI model.',
    alt: 'Request detail for a request blocked by policy because it contained a social security number',
  },
  {
    id: 'dashboard',
    tab: 'Dashboard',
    title: 'Usage, cost and risk at a glance.',
    text: 'Requests, spend and speed for the period, how many requests your rules blocked or flagged, and a budget chart with a projection to the end of the month.',
    alt: 'Dashboard with request, cost and usage cards and a budget chart',
  },
  {
    id: 'policy',
    tab: 'Policy',
    title: 'Your rules, in one place.',
    text: 'Choose whether to observe, record or enforce. Approve models, block sensitive words, then fine-tune data protection, routing, behavior and limits.',
    alt: 'Policy configuration page with enforcement mode, approved models and blocked words',
  },
  {
    id: 'mcp',
    tab: 'AI agent tools',
    title: 'Decide which tools your AI agents can use.',
    text: 'Connect the business tools your agents rely on, lock their definitions so they cannot be changed silently, and screen what comes back.',
    alt: 'Agent tools page listing a connected tool server with its locking and screening settings',
  },
  {
    id: 'logs',
    tab: 'Activity log',
    title: 'Every request on the record.',
    text: 'Outcome, decision, usage and cost for each request, searchable and filterable, with a link to the full detail.',
    alt: 'Activity log table with outcome, policy decision, usage, speed and cost columns',
  },
];

export default function ProductTourSection() {
  const [active, setActive] = useState(SHOTS[0].id);
  const shot = SHOTS.find(s => s.id === active) ?? SHOTS[0];

  return (
    <Section id="tour" label="The product" title={<>One console to see and <em>control all AI use.</em></>} aside="real screens from the demo">
      <div role="tablist" aria-label="Console screens" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 18 }}>
        {SHOTS.map(s => (
          <button
            key={s.id}
            type="button"
            role="tab"
            id={`tour-tab-${s.id}`}
            aria-selected={s.id === active}
            aria-controls="tour-panel"
            className={s.id === active ? 'opa-btn opa-btn-primary' : 'opa-btn'}
            onClick={() => setActive(s.id)}
          >{s.tab}</button>
        ))}
      </div>

      <div id="tour-panel" role="tabpanel" aria-labelledby={`tour-tab-${shot.id}`} className="split tour-split">
        <div>
          <h3 style={{ margin: '0 0 10px', fontFamily: 'var(--sans)', fontSize: 20, fontWeight: 500, letterSpacing: '-0.02em', color: 'var(--ink)' }}>{shot.title}</h3>
          <p className="lede">{shot.text}</p>
          <p className="note">Demo with sample data, not a customer.</p>
        </div>
        <figure className="frame" style={{ margin: 0 }}>
          <div className="frame-bar" aria-hidden="true"><i /><i /><i /><span>OpenProxyAI · demo organization</span></div>
          <img src={`/images/console/${shot.id}.webp`} width={1440} height={900} alt={shot.alt} loading="lazy" decoding="async" style={{ display: 'block', width: '100%', height: 'auto' }} />
        </figure>
      </div>
    </Section>
  );
}
