import PillarPage from '../components/PillarPage';
import { pageMeta } from '../site/meta';

export function meta() {
  return pageMeta({ title: 'FinOps — OpenProxyAI', description: 'Budgets per org, team and user, anomaly detection, month-end projection and chargeback labels.', path: '/finops' });
}

export default function FinopsRoute() {
  return (
    <PillarPage
      pillar="finops"
      sceneId="finops"
      eyebrow="FinOps"
      title="Every token has an owner and a budget."
      lede="Spend is tracked per request and attributed to a team before the bill arrives. Over budget means HTTP 402, not a surprise invoice."
    />
  );
}
