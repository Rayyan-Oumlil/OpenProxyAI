import PillarPage from '../components/PillarPage';
import { pageMeta } from '../site/meta';

export function meta() {
  return pageMeta({ title: 'Agents — OpenProxyAI', description: 'An MCP gateway with per-agent identity, tool policies, guardrails on tool calls and agent-to-agent audit.', path: '/agents' });
}

export default function AgentsRoute() {
  return (
    <PillarPage
      pillar="agents"
      sceneId="agents"
      eyebrow="Agents"
      title="Know what every agent did, with which tool, on whose behalf."
      lede="Agents reach tools only through the gateway. Each has an identity, a tool allowlist and a budget — and every call lands in the audit log."
    />
  );
}
