import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { apiClient } from "../../api/client";
import type { ProviderKeyResponse } from "../../api/types";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { PageHeader } from "../../components/ui/PageHeader";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { formatDateTime, formatLatency, formatPercent } from "../../lib/utils";
import { useAuth } from "../../state/AuthContext";
import { keyState, lacksAdaptiveData, neverChecked, summarize, type KeyHealth } from "./health";

const REFRESH_MS = 15_000;

const SUMMARY_ORDER: { health: KeyHealth; label: string }[] = [
  { health: "healthy", label: "Healthy" },
  { health: "degraded", label: "Degraded" },
  { health: "down", label: "Down" },
  { health: "unknown", label: "Not checked" },
  { health: "disabled", label: "Disabled" },
];

function weightText(key: ProviderKeyResponse): string {
  if (key.effective_weight == null || key.effective_weight === key.weight) return String(key.weight);
  return `${key.weight} (effective ${key.effective_weight})`;
}

export function ProviderHealthPage() {
  const { token } = useAuth();

  const query = useQuery({
    queryKey: ["provider-keys", token],
    queryFn: () => apiClient.get<ProviderKeyResponse[]>("/api/v1/provider-keys", token!),
    enabled: Boolean(token),
    refetchInterval: REFRESH_MS,
  });

  // The data's own timestamp is "now" for circuit expiry, so rendering stays a pure function of the query.
  const nowMs = query.dataUpdatedAt;
  const keys = query.data ?? [];

  const columns: Column<ProviderKeyResponse>[] = [
    {
      key: "key",
      header: "Key",
      cell: (k) => (
        <div>
          <div>{k.key_alias}</div>
          <div className="mcp-tool-desc">
            {k.provider} · {k.region.toUpperCase()}
          </div>
        </div>
      ),
    },
    {
      key: "state",
      header: "State",
      cell: (k) => {
        const state = keyState(k, nowMs);
        return (
          <div>
            <StatusBadge verdict={state.verdict}>{state.label}</StatusBadge>
            <div className="mcp-tool-desc">{state.reason}</div>
          </div>
        );
      },
    },
    {
      key: "checked",
      header: "Last health check",
      nowrap: true,
      cell: (k) => (k.last_health_check_at ? formatDateTime(k.last_health_check_at) : "Never"),
    },
    { key: "p99", header: "p99 latency", align: "right", mono: true, cell: (k) => (k.latency_p99_ms != null ? formatLatency(k.latency_p99_ms) : "—") },
    { key: "errors", header: "Error rate", align: "right", mono: true, cell: (k) => (k.error_rate != null ? formatPercent(k.error_rate) : "—") },
    { key: "weight", header: "Weight", align: "right", mono: true, cell: weightText },
  ];

  const summary = summarize(keys, nowMs);

  return (
    <section className="page-wrap">
      <PageHeader
        title="Provider health"
        description="Whether each provider key can take traffic right now. Refreshes every 15 seconds."
        actions={
          <Link to="/provider-keys" className="btn-outline">
            Manage keys
          </Link>
        }
      />

      {keys.length > 0 ? (
        <ul className="health-summary" aria-label="Keys by state">
          {SUMMARY_ORDER.map(({ health, label }) => (
            <li key={health} className="health-summary__item">
              <span className="health-summary__count">{summary[health]}</span>
              <span>{label}</span>
            </li>
          ))}
        </ul>
      ) : null}

      {neverChecked(keys) ? (
        <p className="trace-note" role="status">
          No health check has run yet. Set PROVIDER_HEALTH_CHECK_ENABLED to ping keys every 5 minutes.
        </p>
      ) : null}
      {lacksAdaptiveData(keys) ? (
        <p className="trace-note" role="status">
          No latency or error data. Enable ADAPTIVE_LB_ENABLED and send traffic to see p99 and error rate per key.
        </p>
      ) : null}

      <DataTable
        caption="Provider key health"
        columns={columns}
        rows={query.data}
        getRowId={(k) => k.id}
        isLoading={query.isLoading}
        error={
          query.isError
            ? {
                title: "Unable to load provider health",
                detail: query.error instanceof Error ? query.error.message : "Unknown error",
                onRetry: () => void query.refetch(),
              }
            : null
        }
        empty={{ title: "No provider keys", detail: "Add a provider key to route traffic to an LLM provider." }}
      />
    </section>
  );
}
