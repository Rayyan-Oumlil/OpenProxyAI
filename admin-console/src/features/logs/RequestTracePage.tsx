import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { apiClient } from "../../api/client";
import type { RequestLogDetail } from "../../api/types";
import { ErrorState } from "../../components/ErrorState";
import { LoadingState } from "../../components/LoadingState";
import { PageHeader } from "../../components/ui/PageHeader";
import { StatusBadge, verdictForPolicyAction } from "../../components/ui/StatusBadge";
import { formatCost, formatDateTime, formatLatency, formatNumber } from "../../lib/utils";
import { useAuth } from "../../state/AuthContext";
import { Fact } from "../../components/ui/Fact";
import { describeDataClass } from "../../lib/dataClasses";
import { routingOutcome } from "../../lib/routing";
import { buildTrace, type Trace, type TraceRouting } from "./trace";

function Waterfall({ trace }: { trace: Trace }) {
  return (
    <section className="trace-panel" aria-labelledby="trace-waterfall-title">
      <h2 id="trace-waterfall-title">Where the time went</h2>
      {trace.hasTimings ? (
        <ol className="trace-rows">
          {trace.stages.some((stage) => stage.name === "auth") ? null : (
            // Rows logged before authentication was timed.
            <li className="trace-row trace-row--untimed">
              <span className="trace-row__label">Authentication</span>
              <span className="trace-row__ms">not timed</span>
              <span className="trace-row__track" aria-hidden="true" />
            </li>
          )}
          {trace.stages.map((stage, index) => (
            <li key={`${stage.name}-${index}`} className="trace-row">
              <span className="trace-row__label">{stage.label}</span>
              <span className="trace-row__ms">{formatLatency(stage.ms)}</span>
              <span className="trace-row__track" aria-hidden="true">
                <span className="trace-row__bar" data-stage={stage.name} style={{ left: `${stage.leftPct}%`, width: `${stage.widthPct}%` }} />
              </span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="trace-note">
          Stage timings are not available for this request. Requests logged before timings were added, and embeddings, are not timed.
        </p>
      )}
      {trace.totalMs !== null ? <p className="trace-total">Total {formatLatency(trace.totalMs)}</p> : null}
    </section>
  );
}

function cacheText(trace: Trace): string {
  if (!trace.stages.some((s) => s.name === "cache")) return "Not consulted";
  return trace.cacheTier === "miss" || trace.cacheTier === null ? "Miss" : `Hit (${trace.cacheTier})`;
}

function dataClassText(trace: Trace): string | null {
  const dc = trace.dataClass;
  return dc ? describeDataClass(dc.name, dc.source, dc.entities) : null;
}

function RoutingFact({ routing }: { routing: TraceRouting }) {
  const refused = routing.model === null;
  return (
    <Fact label="Routing">
      {routing.mode === "log_only" ? "Preview, not enforced: " : null}
      {routingOutcome(routing)}
      {refused && routing.authorized.length > 0 ? (
        <span className="trace-fact__detail"> · Authorized for this request: {routing.authorized.slice(0, 5).join(", ")}</span>
      ) : null}
      {routing.experimentSkipped ? <span className="trace-fact__detail"> · Experiment skipped: {routing.experimentSkipped}</span> : null}
      {routing.fallbackRefused ? <span className="trace-fact__detail"> · Fallback model refused: {routing.fallbackRefused}</span> : null}
    </Fact>
  );
}

function Outcome({ detail, trace }: { detail: RequestLogDetail; trace: Trace }) {
  const reachedUpstream = trace.stages.some((s) => s.name === "upstream");
  return (
    <section className="trace-panel" aria-labelledby="trace-outcome-title">
      <h2 id="trace-outcome-title">What happened</h2>
      <dl className="trace-facts">
        <Fact label="Policy">
          <StatusBadge verdict={verdictForPolicyAction(detail.policy_action)} />
          {detail.policy_reason ? <span className="trace-fact__detail"> {detail.policy_reason}</span> : null}
          {detail.policy_triggered_rules && detail.policy_triggered_rules.length > 0 ? (
            <span className="trace-fact__detail"> Rules: {detail.policy_triggered_rules.join(", ")}</span>
          ) : null}
        </Fact>
        {dataClassText(trace) ? <Fact label="Data class">{dataClassText(trace)}</Fact> : null}
        {trace.routing ? <RoutingFact routing={trace.routing} /> : null}
        {trace.callerMessage ? <Fact label="Caller was told">{trace.callerMessage}</Fact> : null}
        <Fact label="Cache">{cacheText(trace)}</Fact>
        <Fact label="Upstream">
          {reachedUpstream || detail.status === "success"
            ? `${detail.provider} · ${detail.model}${detail.ttft_ms != null ? ` · first token ${formatLatency(detail.ttft_ms)}` : ""}`
            : "Not reached"}
          {trace.fallbackCount > 0 ? (
            <span className="trace-fact__detail">
              {" "}
              {trace.fallbackCount} fallback{trace.fallbackCount === 1 ? "" : "s"}
              {trace.fallbackModel ? ` (to ${trace.fallbackModel})` : ""}
            </span>
          ) : null}
        </Fact>
        <Fact label="Usage">
          {formatNumber(detail.prompt_tokens)} prompt + {formatNumber(detail.completion_tokens)} completion = {formatNumber(detail.total_tokens)} tokens ·{" "}
          {formatCost(detail.cost_usd)}
        </Fact>
        {trace.taintRemoved.length > 0 ? <Fact label="Tools removed by taint">{trace.taintRemoved.join(", ")}</Fact> : null}
        {detail.error_message ? <Fact label="Error">{detail.error_message}</Fact> : null}
        {detail.request_id ? (
          <Fact label="Request ID">
            <code>{detail.request_id}</code>
          </Fact>
        ) : null}
      </dl>
    </section>
  );
}

export function RequestTracePage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();

  const query = useQuery({
    queryKey: ["log-detail", id, token],
    queryFn: () => apiClient.get<RequestLogDetail>(`/api/v1/analytics/logs/${id}`, token!),
    enabled: Boolean(id && token),
  });

  if (query.isLoading) return <LoadingState label="Loading request trace..." />;
  if (query.isError || !query.data) {
    return (
      <ErrorState
        title="Unable to load this request"
        detail={query.error instanceof Error ? query.error.message : "Request not found"}
      />
    );
  }

  const detail = query.data;
  const trace = buildTrace(detail);

  return (
    <section className="page-wrap">
      <PageHeader
        title="Request trace"
        description={`${detail.model} · ${formatDateTime(detail.created_at)} · ${detail.status === "success" ? "succeeded" : "failed"}`}
        actions={
          <Link to="/logs" className="btn-outline">
            <ArrowLeft size={14} aria-hidden /> Request logs
          </Link>
        }
      />
      <Waterfall trace={trace} />
      <Outcome detail={detail} trace={trace} />
    </section>
  );
}
