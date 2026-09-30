import { Link } from 'react-router';
import ControlMap from '../map/ControlMap';
import { SCENES } from '../map/scenes';

export function meta() {
  return [{ title: 'Not found — OpenProxyAI' }, { name: 'robots', content: 'noindex' }];
}

export default function NotFoundRoute() {
  return (
    <main className="mx-auto max-w-page px-4 py-16 sm:px-6 md:py-24">
      <p className="font-mono text-step--1 text-danger">404 · no route to this node</p>
      <h1 className="mt-4 text-step-3 font-semibold tracking-tight">This path isn't on the map.</h1>
      <Link to="/" className="mt-6 inline-block rounded-md bg-signal px-4 py-2 font-semibold text-bg">Back to the control plane</Link>
      <ControlMap scene={SCENES.home} animate={false} className="mt-12 opacity-50" />
    </main>
  );
}
