import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import PageCta from '../components/PageCta';
import Section from '../components/Section';
import { docsPage } from '../lib/links';

interface Link { label: string; slug: string }

const APPROACHES = [
  { n: '01', t: 'Ban AI at work', d: 'Simple to announce, hard to hold.' },
  { n: '02', t: 'Rely on each AI vendor', d: 'A different set of controls for every product.' },
  { n: '03', t: 'Build your own', d: 'Full control, and a permanent engineering job.' },
  { n: '04', t: 'OpenProxyAI', d: 'One checkpoint, in your environment, with a record.', us: true },
];

const COLUMNS = ['Ban AI at work', 'Rely on each AI vendor', 'Build your own', 'OpenProxyAI'];
const ROWS: Array<{ q: string; cells: [string, string, string, string] }> = [
  { q: 'Can staff still use AI for their work?', cells: ['No', 'Yes', 'Yes', 'Yes'] },
  { q: 'Is sensitive data checked before it leaves?', cells: ['Only if nobody works around the ban', 'Depends on each vendor’s own settings', 'Once you have built it', 'On every request'] },
  { q: 'Is there one set of rules for every model and tool?', cells: ['Not applicable', 'One set per vendor', 'Once you have built it', 'One policy'] },
  { q: 'Are AI agents limited to approved tools?', cells: ['Not applicable', 'Varies by vendor', 'Once you have built it', 'Per team or application'] },
  { q: 'Is there a single record for auditors?', cells: ['Nothing to record', 'Spread across vendors', 'If you build and maintain it', 'One record, exportable'] },
  { q: 'Does it stay in your environment?', cells: ['Not applicable', 'Held by each vendor', 'Yes', 'Yes'] },
  { q: 'Who keeps it up to date?', cells: ['Nobody', 'Each vendor, separately', 'Your own engineers', 'Shared with the open-source project'] },
];

const DECISIONS: { need: string; link: Link }[] = [
  { need: 'Decide whether a gateway is worth it', link: { label: 'Why every company needs an LLM gateway', slug: 'why-every-company-needs-an-llm-gateway' } },
  { need: 'Choose between building and adopting', link: { label: 'Build vs. buy an LLM gateway', slug: 'build-vs-buy-llm-gateway' } },
  { need: 'Tell an API gateway from an AI gateway', link: { label: 'API gateway or AI gateway', slug: 'api-gateway-or-ai-gateway' } },
  { need: 'Test any vendor’s answers', link: { label: 'An AI gateway buyer’s checklist', slug: 'ai-gateway-buyers-checklist' } },
  { need: 'Run the gateway yourself', link: { label: 'Self-hosted LLM gateway guide', slug: 'self-hosted-llm-gateway-guide' } },
  { need: 'Meet regulated-industry requirements', link: { label: 'An LLM gateway for regulated teams', slug: 'llm-gateway-for-regulated-industries' } },
];

const TOOLS: Link[] = [
  { label: 'OpenProxyAI vs. LiteLLM', slug: 'openproxyai-vs-litellm' },
  { label: 'OpenProxyAI vs. Portkey', slug: 'openproxyai-vs-portkey' },
  { label: 'OpenProxyAI vs. Helicone', slug: 'openproxyai-vs-helicone' },
  { label: 'OpenProxyAI vs. Kong AI Gateway', slug: 'openproxyai-vs-kong-ai-gateway' },
  { label: 'OpenProxyAI vs. Cloudflare AI Gateway', slug: 'openproxyai-vs-cloudflare-ai-gateway' },
  { label: 'OpenProxyAI vs. OpenRouter', slug: 'openproxyai-vs-openrouter' },
  { label: 'OpenProxyAI vs. LangChain', slug: 'openproxyai-vs-langchain' },
];

const blog = (slug: string): string => docsPage(`/blog/${slug}`);

export default function ComparePage() {
  useEffect(() => { document.title = 'Compare LLM gateways | OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Compare"
        title={<>Four ways to handle AI <span style={{ color: 'var(--soft)' }}>at a regulated company.</span></>}
        description="Most organizations begin with one of the first three. This page sets them side by side on the questions a regulator is likely to ask, then points to dated comparisons with other gateways."
        secondary={{ label: 'See the comparison', href: '#table' }}
        visual={
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(220px, 100%), 1fr))', gap: 14 }}>
            {APPROACHES.map(a => (
              <div key={a.n} style={{ background: '#fff', color: 'var(--ink)', border: '1px solid ' + (a.us ? 'var(--ink)' : 'var(--line-2)'), boxShadow: a.us ? '0 0 0 1px var(--ink)' : 'none', borderRadius: 16, padding: 22, display: 'flex', flexDirection: 'column', gap: 8 }}>
                <span className="mono" style={{ fontSize: 13, color: 'var(--ink-3)' }}>{a.n}</span>
                <span style={{ fontSize: 20, fontWeight: 500, letterSpacing: '-0.015em' }}>{a.t}</span>
                <span style={{ fontSize: 15, color: 'var(--ink-2)' }}>{a.d}</span>
              </div>
            ))}
          </div>
        }
      />
      <Section id="table" label="Side by side" title="The same seven questions, asked of each approach.">
        <div className="tbl-scroll">
          <table className="tbl">
            <thead>
              <tr>
                <th scope="col">What a regulator will ask</th>
                {COLUMNS.map((c, i) => <th key={c} scope="col" style={i === 3 ? { background: 'var(--panel-2)', color: 'var(--ink)' } : undefined}>{c}</th>)}
              </tr>
            </thead>
            <tbody>
              {ROWS.map(r => (
                <tr key={r.q}>
                  <td>{r.q}</td>
                  {r.cells.map((c, i) => <td key={i} style={i === 3 ? { background: 'var(--panel-2)', color: 'var(--ink)' } : undefined}>{c}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
      <Section id="decisions" label="By decision" title="Start from what you need to decide." aside="Articles. Each one is dated and carries its correction notes.">
        <div className="tbl-scroll">
          <table className="tbl">
            <thead><tr><th scope="col">If you need to…</th><th scope="col">Read</th></tr></thead>
            <tbody>
              {DECISIONS.map(d => (
                <tr key={d.need}>
                  <td>{d.need}</td>
                  <td><a href={blog(d.link.slug)} target="_blank" rel="noopener noreferrer">{d.link.label} →</a></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
      <Section id="tools" label="By tool" title="Side by side, one tool at a time." aside="Competitor products change quickly, so every comparison is dated.">
        <ul style={{ listStyle: 'none', margin: 0, padding: 0 }} className="grid-2">
          {TOOLS.map(t => (
            <li key={t.slug}>
              <a className="opa-card" href={blog(t.slug)} target="_blank" rel="noopener noreferrer" style={{ display: 'block', padding: 22, color: 'var(--ink)', textDecoration: 'none', fontSize: 17, fontWeight: 500 }}>
                {t.label} →
              </a>
            </li>
          ))}
        </ul>
        <p className="note">
          Where we differ is governance you host yourself: sensitive data kept where you allow, controlled AI agents and a permanent record.{' '}
          <a href={docsPage('/resources/compare')} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--ink)' }}>Full guide →</a>
        </p>
      </Section>
      <PageCta title="Compare it against what you do today." body="Bring your current AI policy. We will show you how each rule would be applied and recorded." />
    </>
  );
}
