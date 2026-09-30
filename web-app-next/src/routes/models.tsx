import PillarPage from '../components/PillarPage';
import { pageMeta } from '../site/meta';

export function meta() {
  return pageMeta({ title: 'Models — OpenProxyAI', description: 'Routing, failover, circuit breakers, a three-tier cache and data residency across every LLM provider.', path: '/models' });
}

export default function ModelsRoute() {
  return (
    <PillarPage
      pillar="models"
      sceneId="models"
      eyebrow="Models"
      title="Every provider behind one reliable endpoint."
      lede="Weighted keys, automatic fallback, circuit breakers and caching — so an outage or a price change is a config edit, not an incident."
    />
  );
}
