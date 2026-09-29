import type { Scene } from '../types';

export const trust: Scene = {
  id: 'trust',
  title: 'Guardrails and audit',
  description: 'Every prompt passes PII redaction and injection detection before it leaves, and every decision is written to the audit log.',
  viewBox: { w: 1000, h: 560 },
  nodes: [
    { id: 'clinician', kind: 'client', label: 'clinical-notes app', x: 120, y: 200 },
    { id: 'analyst', kind: 'client', label: 'analyst workspace', x: 120, y: 360 },
    { id: 'gw', kind: 'gateway', label: 'policy engine', x: 480, y: 280 },
    { id: 'llm', kind: 'model', label: 'approved model', x: 860, y: 200 },
    { id: 'audit', kind: 'store', label: 'append-only audit', x: 860, y: 400 },
  ],
  edges: [
    { from: 'clinician', to: 'gw' }, { from: 'analyst', to: 'gw' },
    { from: 'gw', to: 'llm' }, { from: 'gw', to: 'audit' },
  ],
  flows: [
    { id: 'clinical', path: ['clinician', 'gw', 'llm'], weights: { redacted: 5, ok: 2, blocked_446: 1 } },
    { id: 'analyst', path: ['analyst', 'gw', 'llm'], weights: { ok: 5, blocked_446: 2, redacted: 1 } },
  ],
};
