import Section from '../../components/Section';

const APPS = ['support-bot', 'finance-app', 'research-agent', 'ops-agent'];
const PROVIDERS = ['OpenAI', 'Anthropic', 'Azure', 'Mistral'];

function Diagram({ governed }: { governed: boolean }) {
  return (
    <svg viewBox="-40 0 460 260" role="img" aria-label={governed ? 'Every app goes through one gateway' : 'Every app calls every provider directly'} className="h-auto w-full">
      {APPS.flatMap((_, a) => (governed
        ? [<line key={`a${a}`} x1={70} y1={40 + a * 60} x2={200} y2={130} stroke="var(--ok)" strokeWidth={1.5} />]
        : PROVIDERS.map((__, p) => <line key={`${a}-${p}`} x1={70} y1={40 + a * 60} x2={330} y2={40 + p * 60} stroke="var(--danger)" strokeOpacity={0.6} />)))}
      {governed && PROVIDERS.map((_, p) => <line key={`p${p}`} x1={200} y1={130} x2={330} y2={40 + p * 60} stroke="var(--ok)" strokeWidth={1.5} />)}
      {APPS.map((name, a) => <text key={name} x={60} y={44 + a * 60} textAnchor="end" fontSize={11} className="fill-ink-dim font-mono">{name}</text>)}
      {PROVIDERS.map((name, p) => <text key={name} x={340} y={44 + p * 60} fontSize={11} className="fill-ink-dim font-mono">{name}</text>)}
      {governed && <circle cx={200} cy={130} r={16} fill="var(--surface)" stroke="var(--signal)" strokeWidth={2} />}
    </svg>
  );
}

export default function WithoutWith() {
  return (
    <Section title="Sixteen unmanaged integrations, or one chokepoint.">
      <div className="grid gap-4 md:grid-cols-2">
        <figure className="rounded-xl border border-line bg-surface p-5">
          <Diagram governed={false} />
          <figcaption className="mt-3 text-ink-dim">Keys in every service, no shared budget, no single audit trail.</figcaption>
        </figure>
        <figure className="rounded-xl border border-signal/40 bg-surface p-5">
          <Diagram governed />
          <figcaption className="mt-3 text-ink-dim">One key per app, one policy, one log — providers swappable behind it.</figcaption>
        </figure>
      </div>
    </Section>
  );
}
