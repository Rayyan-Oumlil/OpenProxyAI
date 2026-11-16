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
    tab: 'Request trace',
    title: 'Open any request and see exactly what happened.',
    text: 'Where the time went, the policy verdict, the data class (here confidential, detected: ssn), what the caller was told, and that the cache was not consulted and the provider was never reached.',
    alt: 'Request trace in the console for a request blocked by policy because it contained an SSN',
  },
  {
    id: 'dashboard',
    tab: 'Dashboard',
    title: 'Spend, volume and policy at a glance.',
    text: 'Requests, cost, tokens and latency for the period, how many requests policy blocked or flagged, and a budget burn-down with a month-end projection.',
    alt: 'Gateway dashboard with request, cost, token and latency cards and a budget burn-down chart',
  },
  {
    id: 'policy',
    tab: 'Policy',
    title: 'One place for what the gateway allows and blocks.',
    text: 'Choose Observe, Log only or Enforce, set a model allowlist and blocked keywords, then tune data protection, data-class routing, behavior and rate limits in the other tabs.',
    alt: 'Policy configuration page with enforcement mode, model allowlist and blocked keywords',
  },
  {
    id: 'mcp',
    tab: 'MCP servers',
    title: 'Bound the tools your agents can reach.',
    text: 'Register tool servers behind one endpoint and set pinning (off, warn, enforce) and an injection scan (off, log, redact, block) for each server.',
    alt: 'MCP servers page listing a server with pinning and injection scan settings',
  },
  {
    id: 'logs',
    tab: 'Request logs',
    title: 'Every request, filterable.',
    text: 'Status, policy decision, tokens, latency and cost for each request, with a detail drawer and a link to the full trace.',
    alt: 'Request logs table with status, policy decision, tokens, latency and cost columns',
  },
];

export default function ProductTourSection() {
  const [active, setActive] = useState(SHOTS[0].id);
  const shot = SHOTS.find(s => s.id === active) ?? SHOTS[0];

  return (
    <Section id="tour" label="§03 · the console" title={<>See what an operator <em>actually gets.</em></>} aside="screenshots of the demo console">
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
          <p className="note">Demo console with seeded sample data, not a customer.</p>
        </div>
        <figure className="frame" style={{ margin: 0 }}>
          <div className="frame-bar" aria-hidden="true"><i /><i /><i /><span>console · demo organization</span></div>
          <img src={`/images/console/${shot.id}.webp`} width={1440} height={900} alt={shot.alt} loading="lazy" decoding="async" style={{ display: 'block', width: '100%', height: 'auto' }} />
        </figure>
      </div>
    </Section>
  );
}
