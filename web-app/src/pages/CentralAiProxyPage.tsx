import { useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import PageCta from '../components/PageCta';
import Section from '../components/Section';
import SubProducts from '../components/SubProducts';
import { CardGrid, KeyValue, Shot } from '../components/blocks';

const code = (s: string) => <code className="mono" style={{ fontSize: 14 }}>{s}</code>;

const ONE_DOOR = [
  { title: 'Everyone goes through it', body: 'Anyone in the company who wants to use generative AI talks to the gateway. Employees, applications and agents never call an AI platform directly.' },
  { title: 'It talks to the outside world', body: 'The gateway is the only thing that reaches out to AI platforms, so it is the only place your provider accounts and keys need to exist.' },
  { title: 'It talks to what is inside', body: 'The same gateway connects people and agents to your local MCP servers and your own language models, safely.' },
];

const OUTSIDE = [
  { k: 'OpenAI', v: 'GPT models and the rest of the OpenAI platform, through one account that your people never see.' },
  { k: 'Anthropic Claude', v: 'Claude models, reached through the same address and the same key as every other model.' },
  { k: 'Perplexity', v: 'Search-grounded answers, behind the same checkpoint as everything else.' },
  { k: 'Any other platform', v: 'Azure, Mistral and more than a hundred others are supported. Add one and it becomes available to everyone at once.' },
];

const INSIDE = [
  { title: 'Local MCP servers', body: 'Your internal tools sit behind one gateway address. Each agent gets only the tools it was granted, tool descriptions are locked once approved, and what tools send back is scanned for hidden instructions.' },
  { title: 'Local language models', body: 'Models you host yourself, such as on vLLM or Ollama, are connected as internal models. Requests that must not leave the company can be kept on them.' },
];

const ONLY_WAY = [
  { k: 'Block direct access', v: 'Use your firewall and DNS to stop the company network from reaching AI platforms directly. The gateway is then the only route that works.' },
  { k: 'Give out gateway keys, not provider keys', v: 'People and applications get gateway keys. The provider keys stay in your secrets store and never reach a laptop or a code repository.' },
  { k: 'Pair it with the browser extension', v: 'Web Browser Control reports the AI sites that people still reach outside the gateway.' },
];

const ENDPOINTS = [
  { k: 'Chat, with streaming', v: <>{code('/v1/chat/completions')} and {code('/v1/responses')}</> },
  { k: 'Embeddings and rerank', v: <>{code('/v1/embeddings')} and {code('/v1/rerank')}</> },
  { k: 'Images and audio', v: <>{code('/v1/images/generations')}, {code('/v1/audio/transcriptions')} and {code('/v1/audio/speech')}</> },
  { k: 'Files and batches', v: <>{code('/v1/files')} and {code('/v1/batches')}</> },
  { k: 'Realtime', v: <>{code('/v1/realtime')} over WebSocket</> },
  { k: 'Agent tools', v: <>{code('/v1/mcp')} for all your MCP servers</> },
];

const INSTALL = [
  { title: 'Docker Compose', body: 'One command starts the gateway, its database, its cache and the console. A demo version uses a fake model, so it needs no provider key.' },
  { title: 'Kubernetes with Helm', body: 'Autoscaling between 2 and 10 replicas, a disruption budget and monitoring hooks.' },
  { title: 'Your own database and cache', body: 'Point the gateway at the PostgreSQL and Redis you already run.' },
  { title: 'Air-gapped', body: 'Turn off every integration that calls out. Calls to the models you configure still go out, as they must.' },
];

export default function CentralAiProxyPage() {
  useEffect(() => { document.title = 'Central AI Proxy | OpenProxyAI'; }, []);

  return (
    <>
      <PageHeader
        eyebrow="Product · Central AI Proxy"
        title={<>The only way into <span style={{ color: 'var(--soft)' }}>generative AI.</span></>}
        description="The Central AI Proxy is a gateway your whole company goes through to use generative AI. It talks to OpenAI, Claude, Perplexity and any other platform for you, and connects safely to your local MCP servers and local models."
        secondary={{ label: 'How it works', href: '#door' }}
        visual={<Shot src="/images/console/dashboard.webp" alt="OpenProxyAI console dashboard: requests, cost, how many requests were stopped or flagged by policy, and the budget for the month." />}
      />
      <Section id="door" label="One gateway" title="One door in, and one door out." aside="Because everything passes through one place, one place is all you have to secure.">
        <CardGrid items={ONE_DOOR} min={260} />
      </Section>
      <Section id="outside" label="To the outside world" title="Any AI platform, behind one address.">
        <KeyValue rows={OUTSIDE} />
      </Section>
      <Section id="inside" label="To your own systems" title="Local tools and local models, reached safely.">
        <CardGrid items={INSIDE} min={300} />
      </Section>
      <Section id="only-way" label="Making it the only way" title="A gateway only helps if nobody walks around it." aside="Three steps turn it from an option into the rule.">
        <KeyValue rows={ONLY_WAY} />
      </Section>
      <Section id="endpoints" label="What it speaks" title="The interfaces your teams already use.">
        <KeyValue rows={ENDPOINTS} />
      </Section>
      <Section id="install" label="Installing it" title="Run it where your data already lives.">
        <CardGrid items={INSTALL} min={240} />
      </Section>
      <SubProducts current="central-ai-proxy" />
      <PageCta title="Make one gateway the only way in." body="We will install the gateway with your platform team, connect one outside platform and one local model, and show you the record of a request through each." />
    </>
  );
}
