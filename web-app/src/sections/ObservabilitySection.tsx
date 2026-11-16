import Section from '../components/Section';
import CodeBlock from '../components/CodeBlock';
import { docsPage } from '../lib/links';

const SIGNALS = [
  { name: 'Prometheus', desc: 'A /metrics endpoint exposes request counts, end-to-end latency, time to first token, tokens, cost, policy violations and rate-limit hits.' },
  { name: 'OpenTelemetry', desc: 'One gen_ai span per finished request and per MCP tool call, as OTLP/HTTP. Prompts and tool arguments are never attached. Off by default.' },
  { name: 'SIEM export', desc: 'A security event for each block, budget stop or rate limit, as CEF or JSON, to stdout, a file or syslog. Off by default, and a broken collector cannot slow a request.' },
];

export default function ObservabilitySection() {
  return (
    <Section id="observability" label="§06 · observability" title={<>Plugs into <em>what you already run.</em></>} aside="opt-in per deployment">
      <div className="split">
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {SIGNALS.map((s, i) => (
            <div key={s.name} style={{ padding: '16px 0', borderTop: i === 0 ? 'none' : '1px solid var(--line)' }}>
              <div style={{ color: 'var(--ink)', fontSize: 13.5, fontWeight: 500, marginBottom: 5 }}>{s.name}</div>
              <p style={{ color: 'var(--ink-2)', fontFamily: 'var(--sans)', fontSize: 14, lineHeight: 1.6, margin: 0 }}>{s.desc}</p>
            </div>
          ))}
          <a className="opa-btn" style={{ alignSelf: 'flex-start', marginTop: 8 }} href={docsPage('/guides/telemetry-and-siem')} target="_blank" rel="noopener noreferrer">$ telemetry and SIEM guide →</a>
        </div>
        <CodeBlock title="GET /metrics" tag="metric names from the code">
          <span className="tok-dim"># metrics the gateway defines (labels vary)</span>{'\n'}
          openproxy_requests_total{'\n'}
          openproxy_request_latency_seconds{'\n'}
          openproxy_ttft_seconds{'\n'}
          openproxy_tokens_total{'\n'}
          openproxy_cost_usd_total{'\n'}
          openproxy_policy_violations_total{'\n'}
          openproxy_rate_limit_hits_total
        </CodeBlock>
      </div>
    </Section>
  );
}
