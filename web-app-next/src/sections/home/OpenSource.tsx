import Section from '../../components/Section';
import stats from '../../data/repo-stats.json';
import { GITHUB_URL } from '../../site/links';

const ITEMS = [
  { value: stats.testFunctions, label: 'backend tests' },
  { value: stats.migrations, label: 'database migrations' },
  { value: stats.routeModules, label: 'API route modules' },
  { value: stats.serviceModules, label: 'services' },
];

export default function OpenSource() {
  return (
    <Section eyebrow="Open source" title="Read the code before you trust the gateway." lede="Counted from the repository at build time.">
      <dl className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {ITEMS.map(i => (
          <div key={i.label} className="rounded-xl border border-line bg-surface p-5">
            <dt className="text-ink-dim">{i.label}</dt>
            <dd className="mt-1 font-mono text-step-3 text-ink">{i.value}</dd>
          </div>
        ))}
      </dl>
      <a href={GITHUB_URL} className="mt-8 inline-block rounded-md bg-signal px-4 py-2 font-semibold text-bg hover:brightness-110">View on GitHub</a>
    </Section>
  );
}
