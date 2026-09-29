import { type RouteConfig, index, route } from '@react-router/dev/routes';

export default [
  index('routes/home.tsx'),
  route('models', 'routes/models.tsx'),
  route('agents', 'routes/agents.tsx'),
  route('trust', 'routes/trust.tsx'),
  route('finops', 'routes/finops.tsx'),
  route('engineering', 'routes/engineering.tsx'),
  route('pricing', 'routes/pricing.tsx'),
  route('*', 'routes/not-found.tsx'),
] satisfies RouteConfig;
