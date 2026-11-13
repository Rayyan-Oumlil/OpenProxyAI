import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import { Badge } from "../../components/ui/badge";
import { useConfirm } from "../../components/ui/ConfirmDialog";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { PageHeader } from "../../components/ui/PageHeader";
import { formatCost, formatDateTime } from "../../lib/utils";
import { useAuth } from "../../state/AuthContext";

const JOBS = "/api/v1/batch-jobs";
const REFRESH_MS = 5000;

export type BatchStatus =
  | "validating"
  | "in_progress"
  | "completed"
  | "failed"
  | "cancelled"
  | "budget_exceeded";

export type BatchJob = {
  id: string;
  status: BatchStatus;
  created_by: string | null;
  total: number;
  completed: number;
  failed: number;
  cost_usd: number;
  max_cost_usd: number;
  error: string | null;
  created_at: string;
  finished_at: string | null;
};

const LABEL: Record<BatchStatus, string> = {
  validating: "Validating",
  in_progress: "Running",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
  budget_exceeded: "Stopped at the cap",
};
const VARIANT: Record<BatchStatus, "success" | "error" | "warning" | "muted" | "policy"> = {
  validating: "policy",
  in_progress: "policy",
  completed: "success",
  failed: "error",
  cancelled: "muted",
  budget_exceeded: "warning",
};

export const isActive = (job: BatchJob) =>
  job.status === "validating" || job.status === "in_progress";

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export function BatchJobsPage() {
  const { token, user } = useAuth();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const isAdmin = user?.role === "admin";

  const jobs = useQuery({
    queryKey: ["batch-jobs", token],
    queryFn: () => apiClient.get<BatchJob[]>(JOBS, token!),
    enabled: Boolean(token) && isAdmin,
    // Poll only while something is running, so an idle page makes no requests.
    refetchInterval: (query) =>
      query.state.data?.some(isActive) ? REFRESH_MS : false,
  });

  const cancel = useMutation({
    mutationFn: (job: BatchJob) =>
      apiClient.post<BatchJob>(`${JOBS}/${job.id}/cancel`, {}, token!),
    onSuccess: () => {
      toast.success("Batch job cancelled. Finished lines are kept.");
      void qc.invalidateQueries({ queryKey: ["batch-jobs"] });
    },
    onError: (e) => {
      toast.error(errorMessage(e, "Could not cancel the batch job"));
      void qc.invalidateQueries({ queryKey: ["batch-jobs"] });
    },
  });

  if (!isAdmin) return <p>You need admin privileges to see batch jobs.</p>;

  const columns: Column<BatchJob>[] = [
    {
      key: "status",
      header: "Status",
      cell: (j) => <Badge variant={VARIANT[j.status]}>{LABEL[j.status]}</Badge>,
    },
    {
      key: "by",
      header: "Started by",
      cell: (j) => j.created_by ?? "Deleted user",
    },
    {
      key: "progress",
      header: "Lines",
      align: "right",
      mono: true,
      cell: (j) =>
        `${j.completed + j.failed} / ${j.total}${j.failed ? ` (${j.failed} failed)` : ""}`,
    },
    {
      key: "cost",
      header: "Cost / cap",
      align: "right",
      mono: true,
      cell: (j) => `${formatCost(j.cost_usd)} / ${formatCost(j.max_cost_usd)}`,
    },
    {
      key: "created",
      header: "Started",
      nowrap: true,
      cell: (j) => formatDateTime(j.created_at),
    },
    {
      key: "error",
      header: "Note",
      cell: (j) => j.error ?? "",
    },
    {
      key: "actions",
      header: "Actions",
      cell: (j) =>
        isActive(j) ? (
          <button
            type="button"
            className="btn-outline btn-small"
            disabled={cancel.isPending}
            onClick={async () => {
              if (
                await confirm({
                  title: "Cancel this batch job?",
                  description: `${j.completed + j.failed} of ${j.total} lines have run. Lines already finished are kept and billed; the rest are not run.`,
                  confirmLabel: "Cancel job",
                  destructive: true,
                })
              )
                cancel.mutate(j);
            }}
          >
            <Ban size={14} className="text-accent-rose" aria-hidden /> Cancel
          </button>
        ) : null,
    },
  ];

  return (
    <div className="page">
      <PageHeader
        title="Batch jobs"
        description="Jobs your applications started with /v1/batches. Every line ran under your policy, routing and budget; this page shows progress and cost, never the content."
      />
      <DataTable
        caption="Batch jobs"
        columns={columns}
        rows={jobs.data}
        getRowId={(j) => j.id}
        isLoading={jobs.isLoading}
        error={
          jobs.isError
            ? {
                title: "Could not load batch jobs",
                detail: errorMessage(jobs.error, "Unknown error"),
                onRetry: () => void jobs.refetch(),
              }
            : null
        }
        empty={{
          title: "No batch jobs",
          detail:
            "Upload a JSONL file to /v1/files and start it with /v1/batches; it appears here.",
        }}
      />
    </div>
  );
}
