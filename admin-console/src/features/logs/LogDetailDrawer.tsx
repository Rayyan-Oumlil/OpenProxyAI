import { useQuery } from "@tanstack/react-query";
import { Clock, DollarSign, Zap, Hash, Shield, AlertCircle, Copy, Check } from "lucide-react";
import { useState } from "react";

import { apiClient } from "../../api/client";
import type { RequestLogDetail } from "../../api/types";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetBody } from "../../components/ui/sheet";
import { Badge } from "../../components/ui/badge";
import { useAuth } from "../../state/AuthContext";
import { formatCost, formatLatency, formatDate } from "../../lib/utils";

interface LogDetailDrawerProps {
  logId: string | null;
  onClose: () => void;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }
  return (
    <button
      type="button"
      onClick={copy}
      title="Copy to clipboard"
      style={{
        border: "none",
        background: "transparent",
        padding: "2px 4px",
        cursor: "pointer",
        color: "var(--muted)",
      }}
    >
      {copied ? <Check size={13} /> : <Copy size={13} />}
    </button>
  );
}

function DetailRow({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 py-2" style={{ borderBottom: "1px solid var(--line)" }}>
      <Icon size={14} style={{ color: "var(--muted)", marginTop: 2, flexShrink: 0 }} />
      <span style={{ color: "var(--muted)", fontSize: "0.82rem", width: 100, flexShrink: 0 }}>{label}</span>
      <span style={{ fontSize: "0.88rem", fontWeight: 500, wordBreak: "break-all" }}>{value ?? "—"}</span>
    </div>
  );
}

export function LogDetailDrawer({ logId, onClose }: LogDetailDrawerProps) {
  const { token } = useAuth();

  const query = useQuery({
    queryKey: ["log-detail", logId, token],
    queryFn: () => apiClient.get<RequestLogDetail>(`/api/v1/analytics/logs/${logId}`, token!),
    enabled: Boolean(logId && token),
  });

  const d = query.data;

  return (
    <Sheet open={Boolean(logId)} onOpenChange={(open) => { if (!open) onClose(); }}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Request Detail</SheetTitle>
          {d && (
            <span style={{ fontSize: "0.78rem", color: "var(--muted)" }}>
              {formatDate(d.created_at)}
            </span>
          )}
        </SheetHeader>

        <SheetBody>
          {query.isLoading && (
            <div className="flex items-center justify-center py-12">
              <div className="loader" />
            </div>
          )}

          {query.isError && (
            <div
              className="rounded-lg p-4 text-sm"
              style={{ background: "rgba(239,68,68,0.08)", color: "#b91c1c" }}
            >
              Failed to load log detail.
            </div>
          )}

          {d && (
            <div className="flex flex-col gap-0">
              {/* Status + Model badges */}
              <div className="flex flex-wrap gap-2 mb-4">
                <Badge variant={d.status === "success" ? "success" : "error"}>
                  {d.status}
                </Badge>
                <Badge variant="muted">{d.model}</Badge>
                <Badge variant="muted">{d.provider}</Badge>
                {d.policy_action && (
                  <Badge variant="policy">{d.policy_action}</Badge>
                )}
              </div>

              {/* Core metrics */}
              <DetailRow icon={Clock} label="Created" value={new Date(d.created_at).toLocaleString()} />
              <DetailRow icon={Zap} label="Latency" value={d.latency_ms != null ? formatLatency(d.latency_ms) : "—"} />
              <DetailRow icon={Zap} label="TTFT" value={d.ttft_ms != null ? formatLatency(d.ttft_ms) : "—"} />
              <DetailRow
                icon={Hash}
                label="Tokens"
                value={`${d.prompt_tokens} prompt + ${d.completion_tokens} completion = ${d.total_tokens}`}
              />
              <DetailRow icon={DollarSign} label="Cost" value={formatCost(d.cost_usd)} />

              {/* Policy */}
              {d.policy_action && (
                <>
                  <DetailRow icon={Shield} label="Policy" value={d.policy_action} />
                  {d.policy_reason && (
                    <DetailRow icon={Shield} label="Reason" value={d.policy_reason} />
                  )}
                  {d.policy_triggered_rules && d.policy_triggered_rules.length > 0 && (
                    <DetailRow
                      icon={Shield}
                      label="Rules"
                      value={d.policy_triggered_rules.join(", ")}
                    />
                  )}
                </>
              )}

              {/* Error */}
              {d.error_message && (
                <div
                  className="mt-3 rounded-lg p-3 text-sm"
                  style={{ background: "rgba(239,68,68,0.08)", color: "#b91c1c" }}
                >
                  <div className="flex items-center gap-1.5 font-medium mb-1">
                    <AlertCircle size={13} />
                    Error
                  </div>
                  {d.error_message}
                </div>
              )}

              {/* IDs */}
              <div className="mt-4" style={{ borderTop: "1px solid var(--line)", paddingTop: "0.75rem" }}>
                <p className="eyebrow mb-2">Identifiers</p>
                {[
                  ["Log ID", d.id],
                  ["Request ID", d.request_id],
                  ["User ID", d.user_id],
                  ["API Key ID", d.api_key_id],
                ].map(([label, val]) =>
                  val ? (
                    <div
                      key={label as string}
                      className="flex items-center justify-between py-1"
                      style={{ borderBottom: "1px solid var(--line)" }}
                    >
                      <span style={{ color: "var(--muted)", fontSize: "0.8rem" }}>{label}</span>
                      <div className="flex items-center gap-1">
                        <code style={{ fontSize: "0.75rem" }}>{(val as string).slice(0, 16)}…</code>
                        <CopyButton text={val as string} />
                      </div>
                    </div>
                  ) : null
                )}
              </div>

              {/* Raw metadata */}
              {d.request_metadata && (
                <div className="mt-4">
                  <div className="flex items-center justify-between mb-2">
                    <p className="eyebrow">Metadata</p>
                    <CopyButton text={JSON.stringify(d.request_metadata, null, 2)} />
                  </div>
                  <pre
                    style={{
                      background: "var(--bg)",
                      border: "1px solid var(--line)",
                      borderRadius: 8,
                      padding: "0.75rem",
                      fontSize: "0.75rem",
                      overflow: "auto",
                      maxHeight: 240,
                      fontFamily: "JetBrains Mono, Fira Code, monospace",
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {JSON.stringify(d.request_metadata, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </SheetBody>
      </SheetContent>
    </Sheet>
  );
}
