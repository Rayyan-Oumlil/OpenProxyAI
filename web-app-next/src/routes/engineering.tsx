import Section from '../components/Section';
import { CAPABILITIES } from '../data/capabilities';
import { DECISIONS } from '../data/decisions';
import stats from '../data/repo-stats.json';
import { DOCS_URL, GITHUB_URL, sourceUrl } from '../site/links';
import { pageMeta } from '../site/meta';

export function meta() {
  return pageMeta({ title: 'Engineering — OpenProxyAI', description: 'How OpenProxyAI is built: architecture, design decisions and their tradeoffs, and what is shipped versus next.', path: '/engineering' });
}

const STACK = [
  ['Gateway', 'FastAPI (async Python), LiteLLM as a library'],
  ['Data', 'PostgreSQL 16 with row-level security and pgvector'],
  ['Hot path', 'Redis for rate limits, budgets and the L2 cache'],
  ['Analytics', 'Materialized views, optional ClickHouse dual-write'],
  ['Console', 'React, Vite, TypeScript'],
  ['Deploy', 'Docker Compose, Helm, GitHub Actions'],
] as const;

const STATS = [
  [stats.testFunctions, 'backend tests'],
  [stats.testFiles, 'test files'],
  [stats.migrations, 'migrations'],
  [stats.routeModules, 'route modules'],
  [stats.serviceModules, 'services'],
] as const;

export default function EngineeringRoute() {
  const built = CAPABILITIES.filter(c => c.status === 'built');
  const next = CAPABILITIES.filter(c => c.status === 'backlog');
  return (
    <main>
      <section className="mx-auto max-w-page px-4 pb-8 pt-16 sm:px-6 md:pt-24">
        <p className="font-mono text-step--1 uppercase tracking-widest text-signal">Engineering</p>
        <h1 className="mt-4 max-w-3xl text-step-3 font-semibold leading-tight tracking-tight md:text-step-4">How I built OpenProxyAI.</h1>
        <p className="mt-5 max-w-2xl text-step-1 text-ink-dim">
          I designed and built OpenProxyAI end to end — gateway, admin console, deployment. This page is the short version: what it runs on, the decisions that shaped it, and what is shipped versus next.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <a href={GITHUB_URL} className="rounded-md bg-signal px-4 py-2 font-semibold text-bg hover:brightness-110">Source on GitHub</a>
          <a href={DOCS_URL} className="rounded-md border border-line px-4 py-2 text-ink hover:border-ink-dim">Documentation</a>
        </div>
      </section>

      <Section eyebrow="By the numbers" title="Counted from the repository at build time.">
        <dl className="grid grid-cols-2 gap-4 md:grid-cols-5">
          {STATS.map(([value, label]) => (
            <div key={label} className="rounded-xl border border-line bg-surface p-5">
              <dt className="text-ink-dim">{label}</dt>
              <dd className="mt-1 font-mono text-step-3">{value}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section eyebrow="Stack" title="Boring where it can be, specific where it matters.">
        <dl className="grid gap-x-8 gap-y-4 md:grid-cols-2">
          {STACK.map(([k, v]) => (
            <div key={k} className="flex gap-4 border-b border-line pb-3">
              <dt className="w-28 shrink-0 font-mono text-step--1 text-ink-dim">{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section eyebrow="Decisions" title="The tradeoffs behind the design.">
        <ul className="grid gap-4 md:grid-cols-2">
          {DECISIONS.map(d => (
            <li key={d.title} className="min-w-0 rounded-xl border border-line bg-surface p-5">
              <h3 className="text-step-1 font-semibold">{d.title}</h3>
              <p className="mt-2">{d.choice}</p>
              <p className="mt-2 text-ink-dim"><span className="text-signal">Tradeoff:</span> {d.tradeoff}</p>
              <a href={sourceUrl(d.source)} className="mt-3 inline-block break-all font-mono text-step--1 text-ok hover:underline">{d.source} ↗</a>
            </li>
          ))}
        </ul>
      </Section>

      <Section eyebrow="Status" title="Shipped, and next.">
        <div className="grid gap-8 md:grid-cols-2">
          <div>
            <h3 className="font-mono text-step--1 uppercase tracking-widest text-ok">Shipped</h3>
            <ul aria-label="Shipped" className="mt-3 space-y-2">
              {built.map(c => (
                <li key={c.id}><a href={sourceUrl(c.source)} className="hover:text-signal">{c.title}</a></li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="font-mono text-step--1 uppercase tracking-widest text-signal">Next</h3>
            <ul aria-label="Next" className="mt-3 space-y-2">
              {next.map(c => <li key={c.id}>{c.title}</li>)}
            </ul>
          </div>
        </div>
      </Section>
    </main>
  );
}
