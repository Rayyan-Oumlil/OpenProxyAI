import type { RequestLogDetail } from "../../api/types";

export interface TraceStage {
  name: string;
  label: string;
  startMs: number;
  ms: number;
  /** Bar position and width as percentages of the whole request, for the waterfall. */
  leftPct: number;
  widthPct: number;
}

export interface Trace {
  totalMs: number | null;
  stages: TraceStage[];
  /** False for rows logged before stage timings existed; the page says so instead of drawing bars. */
  hasTimings: boolean;
  cacheTier: string | null;
  fallbackCount: number;
  fallbackModel: string | null;
  taintRemoved: string[];
  /** How sensitive the request was judged to be, and why; null for rows logged before classification existed. */
  dataClass: { name: string; source: string; entities: string[] } | null;
  /** Which registry model was authorized to serve the request, and why; null when routing was off or the row is older. */
  routing: TraceRouting | null;
}

export interface TraceRouting {
  mode: string;
  requested: string;
  /** The model chosen, or null when none was authorized. */
  model: string | null;
  reason: string;
  authorized: string[];
  /** Why each other registry model was ruled out. */
  excluded: Record<string, string>;
  experimentSkipped: string | null;
  fallbackRefused: string | null;
}

const LABELS: Record<string, string> = {
  auth: "Authentication",
  policy: "Policy checks",
  classify: "Data classification",
  route: "Routing",
  rate_limit: "Rate limit and budget",
  cache: "Cache lookup",
  upstream: "Upstream call",
};

/** A bar is never thinner than this, so a 0 ms stage is still visible as a tick. */
const MIN_WIDTH_PCT = 0.6;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function nonNegative(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
}

function readStages(metadata: Record<string, unknown>): { name: string; startMs: number; ms: number }[] {
  const raw = metadata.stages;
  if (!Array.isArray(raw)) return [];
  const stages: { name: string; startMs: number; ms: number }[] = [];
  for (const entry of raw) {
    if (!isRecord(entry) || typeof entry.name !== "string") continue;
    const startMs = nonNegative(entry.start_ms);
    const ms = nonNegative(entry.ms);
    if (startMs === null || ms === null) continue;
    stages.push({ name: entry.name, startMs, ms });
  }
  return stages;
}

/** Turns a log detail into what the trace page draws. Metadata is untrusted JSON, so every field is checked. */
export function buildTrace(detail: RequestLogDetail): Trace {
  const metadata = isRecord(detail.request_metadata) ? detail.request_metadata : {};
  const parsed = readStages(metadata);

  const end = parsed.reduce((latest, s) => Math.max(latest, s.startMs + s.ms), 0);
  const logged = nonNegative(detail.latency_ms);
  const totalMs = logged !== null ? Math.max(logged, end) : parsed.length > 0 ? end : null;
  const scale = totalMs && totalMs > 0 ? totalMs : 1;

  const stages = parsed.map((s) => {
    const widthPct = Math.min(100, Math.max((s.ms / scale) * 100, MIN_WIDTH_PCT));
    const leftPct = Math.min((s.startMs / scale) * 100, 100 - widthPct);
    return { name: s.name, label: LABELS[s.name] ?? s.name, startMs: s.startMs, ms: s.ms, leftPct, widthPct };
  });

  const taint = isRecord(metadata.tool_taint) ? metadata.tool_taint : {};
  const dc = isRecord(metadata.data_class) ? metadata.data_class : null;
  const dataClass =
    dc && typeof dc.class === "string"
      ? {
          name: dc.class,
          source: typeof dc.source === "string" ? dc.source : "default",
          entities: Array.isArray(dc.entities) ? dc.entities.filter((e): e is string => typeof e === "string") : [],
        }
      : null;
  const rt = isRecord(metadata.routing) ? metadata.routing : null;
  const routing: TraceRouting | null =
    rt && typeof rt.reason === "string"
      ? {
          mode: typeof rt.mode === "string" ? rt.mode : "enforce",
          requested: typeof rt.requested === "string" ? rt.requested : "",
          model: typeof rt.model === "string" ? rt.model : null,
          reason: rt.reason,
          authorized: Array.isArray(rt.authorized) ? rt.authorized.filter((m): m is string => typeof m === "string") : [],
          excluded: isRecord(rt.excluded)
            ? Object.fromEntries(Object.entries(rt.excluded).filter((e): e is [string, string] => typeof e[1] === "string"))
            : {},
          experimentSkipped: typeof rt.experiment_skipped === "string" ? rt.experiment_skipped : null,
          fallbackRefused: typeof rt.fallback_model_refused === "string" ? rt.fallback_model_refused : null,
        }
      : null;
  return {
    totalMs,
    stages,
    hasTimings: stages.length > 0,
    cacheTier: typeof metadata.cache === "string" ? metadata.cache : null,
    fallbackCount: nonNegative(metadata.fallback_count) ?? 0,
    fallbackModel: typeof metadata.fallback_model_used === "string" ? metadata.fallback_model_used : null,
    taintRemoved: Array.isArray(taint.removed) ? taint.removed.filter((t): t is string => typeof t === "string") : [],
    dataClass,
    routing,
  };
}
