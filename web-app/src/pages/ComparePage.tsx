import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import Section from '../components/Section';
import { docsPage } from '../lib/links';

interface Link {
  label: string;
  slug: string;
}

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
        title={<>Compare gateways <span style={{ color: 'var(--accent)' }}>honestly.</span></>}
        description="Each comparison says where OpenProxyAI differs and when the other tool is the better fit. Competitor products change quickly, so every post is dated and carries its correction notes."
      />
      <Section id="decisions" label="§01 · by decision" title={<>Start from <em>what you need to decide.</em></>} aside="blog posts">
        <div className="opa-card tbl-scroll">
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
      <Section id="tools" label="§02 · by tool" title={<>Side by side, <em>one tool at a time.</em></>} aside="dated comparisons">
        <ul style={{ listStyle: 'none', margin: 0, padding: 0 }} className="grid-2">
          {TOOLS.map(t => (
            <li key={t.slug}>
              <a className="opa-card" href={blog(t.slug)} target="_blank" rel="noopener noreferrer" style={{ display: 'block', padding: 18, color: 'var(--ink)', textDecoration: 'none', fontSize: 14 }}>
                {t.label} <span style={{ color: 'var(--accent)' }}>→</span>
              </a>
            </li>
          ))}
        </ul>
        <p className="note">
          Where we differ is governance: data-class routing with no silent fallback, bounded MCP tools and an audit trail you host. If you only need one SDK for many providers, a lighter tool may serve you better, and the posts say so.{' '}
          <a href={docsPage('/resources/compare')} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>Full guide →</a>
        </p>
      </Section>
    </>
  );
}
