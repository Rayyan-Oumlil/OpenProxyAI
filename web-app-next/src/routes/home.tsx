import Deploy from '../sections/home/Deploy';
import DropIn from '../sections/home/DropIn';
import FollowRequest from '../sections/home/FollowRequest';
import Hero from '../sections/home/Hero';
import OpenSource from '../sections/home/OpenSource';
import Pillars from '../sections/home/Pillars';
import WithoutWith from '../sections/home/WithoutWith';
import { pageMeta } from '../site/meta';

export function meta() {
  return pageMeta({
    title: 'OpenProxyAI — The control plane for enterprise AI',
    description: 'One gateway for every model call and every agent action: routing, budgets, guardrails, and a tamper-evident audit trail.',
    path: '/',
  });
}

export default function HomeRoute() {
  return (
    <main>
      <Hero />
      <FollowRequest />
      <Pillars />
      <DropIn />
      <WithoutWith />
      <Deploy />
      <OpenSource />
    </main>
  );
}
