import { Cloud, Building2, WifiOff } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import Section from '../components/Section';
import { docsPage, GITHUB_URL } from '../lib/links';

interface Place {
  icon: LucideIcon;
  title: string;
  text: string;
}

const PLACES: Place[] = [
  { icon: Cloud, title: 'Your cloud', text: 'Run it in the cloud account you already control and secure.' },
  { icon: Building2, title: 'Your data center', text: 'Keep it on your own infrastructure, next to your other systems.' },
  { icon: WifiOff, title: 'Fully offline', text: 'An air-gapped mode for environments with no outside connection.' },
];

const POINTS = [
  { title: 'Your accounts, your contracts', text: 'You keep your own agreements and keys with each AI provider. They stay in your secrets manager.' },
  { title: 'Open source you can inspect', text: 'Your security team can read the code. Every claim on this site points to a document, a test or the code.' },
  { title: 'Separate by design', text: 'Each organization’s data is kept apart, so one business unit cannot see another’s.' },
];

export default function DeploySection() {
  return (
    <Section id="deploy" label="Deployment" title={<>You decide <em>where it runs.</em></>} aside="self-hosted, no hosted service">
      <div className="grid-3" style={{ marginBottom: 28 }}>
        {PLACES.map(p => (
          <div key={p.title} className="opa-card" style={{ padding: 22, textAlign: 'center' }}>
            <span style={{ width: 44, height: 44, borderRadius: 12, background: 'color-mix(in srgb, var(--accent) 12%, var(--bg))', color: 'var(--accent)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: 12 }}>
              <p.icon size={22} aria-hidden="true" />
            </span>
            <h3 style={{ margin: '0 0 6px', color: 'var(--ink)', fontSize: 16, fontWeight: 600 }}>{p.title}</h3>
            <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 14.5, lineHeight: 1.55, color: 'var(--ink-2)' }}>{p.text}</p>
          </div>
        ))}
      </div>
      <div className="grid-3">
        {POINTS.map(p => (
          <div key={p.title} style={{ borderLeft: '3px solid var(--accent)', paddingLeft: 16 }}>
            <div style={{ color: 'var(--ink)', fontSize: 15, fontWeight: 600, marginBottom: 4 }}>{p.title}</div>
            <p style={{ margin: 0, fontFamily: 'var(--sans)', fontSize: 14.5, lineHeight: 1.6, color: 'var(--ink-2)' }}>{p.text}</p>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 24 }}>
        <a className="opa-btn" href={docsPage('/guides/deployment')} target="_blank" rel="noopener noreferrer">Deployment guide</a>
        <a className="opa-btn" href={GITHUB_URL} target="_blank" rel="noopener noreferrer" data-track="cta_github">View the source</a>
      </div>
    </Section>
  );
}
