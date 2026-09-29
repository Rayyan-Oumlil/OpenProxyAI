export type NodeKind = 'client' | 'agent' | 'gateway' | 'model' | 'tool' | 'store';
export interface MapNode { id: string; kind: NodeKind; label: string; x: number; y: number }
export interface MapEdge { from: string; to: string }
export type Outcome = 'ok' | 'cache_hit' | 'redacted' | 'blocked_446' | 'budget_402' | 'rate_429';
export type StageName = 'auth' | 'rate_limit' | 'policy' | 'cache' | 'route' | 'upstream' | 'log';
export interface FlowSpec { id: string; path: string[]; weights: Partial<Record<Outcome, number>> }
export interface Scene { id: string; title: string; description: string; viewBox: { w: number; h: number }; nodes: MapNode[]; edges: MapEdge[]; flows: FlowSpec[] }
export interface StageResult { stage: StageName; status: 'pass' | 'fail' | 'skip'; detail: string }
export interface RequestEvent { id: string; flowId: string; path: string[]; outcome: Outcome; statusCode: number; stages: StageResult[]; headers: Record<string, string>; atMs: number }
