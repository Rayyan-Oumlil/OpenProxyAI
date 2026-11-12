import { useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../../api/client";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { PageHeader } from "../../components/ui/PageHeader";
import { formatDateTime } from "../../lib/utils";
import { useAuth } from "../../state/AuthContext";

const SCORES = "/api/v1/scores";

type Group = {
  group: string;
  count: number;
  mean: number;
  min: number;
  max: number;
};
type Summary = { group_by: string; groups: Group[] };
type Score = {
  id: string;
  request_id: string;
  score_name: string;
  value: number;
  source: string;
  comment: string | null;
  model: string | null;
  created_at: string;
};

const GROUPS = [
  { value: "score_name", label: "Score name" },
  { value: "model", label: "Model" },
  { value: "day", label: "Day" },
];

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Could not load scores";
}

export function ScoresPage() {
  const { token, user } = useAuth();
  const ids = { by: useId(), name: useId() };
  const role = user?.role ?? "";
  const canSummarize = role === "admin" || role === "developer";
  const isAdmin = role === "admin";
  const [groupBy, setGroupBy] = useState("score_name");
  const [name, setName] = useState("");
  const filter = name.trim()
    ? `&score_name=${encodeURIComponent(name.trim())}`
    : "";

  const summary = useQuery({
    queryKey: ["scores-summary", groupBy, name, token],
    queryFn: () =>
      apiClient.get<Summary>(
        `${SCORES}/summary?group_by=${groupBy}${filter}`,
        token!,
      ),
    enabled: Boolean(token) && canSummarize,
  });
  const recent = useQuery({
    queryKey: ["scores-list", name, token],
    queryFn: () =>
      apiClient.get<Score[]>(`${SCORES}?limit=50${filter}`, token!),
    enabled: Boolean(token) && isAdmin,
  });

  if (!canSummarize)
    return <p>You need developer or admin privileges to read scores.</p>;

  const groupColumns: Column<Group>[] = [
    {
      key: "group",
      header: GROUPS.find((g) => g.value === groupBy)?.label ?? "Group",
      cell: (g) => <span className="font-medium">{g.group}</span>,
    },
    {
      key: "count",
      header: "Scores",
      align: "right",
      mono: true,
      cell: (g) => g.count,
    },
    {
      key: "mean",
      header: "Mean",
      align: "right",
      mono: true,
      cell: (g) => g.mean,
    },
    {
      key: "min",
      header: "Min",
      align: "right",
      mono: true,
      cell: (g) => g.min,
    },
    {
      key: "max",
      header: "Max",
      align: "right",
      mono: true,
      cell: (g) => g.max,
    },
  ];
  const scoreColumns: Column<Score>[] = [
    {
      key: "when",
      header: "When",
      nowrap: true,
      cell: (s) => formatDateTime(s.created_at),
    },
    { key: "name", header: "Score", cell: (s) => s.score_name },
    {
      key: "value",
      header: "Value",
      align: "right",
      mono: true,
      cell: (s) => s.value,
    },
    { key: "model", header: "Model", mono: true, cell: (s) => s.model ?? "—" },
    { key: "source", header: "Source", cell: (s) => s.source },
    {
      key: "comment",
      header: "Comment",
      cell: (s) =>
        s.comment ? (
          <span className="text-sm">{s.comment}</span>
        ) : (
          <span className="text-muted">—</span>
        ),
    },
  ];

  return (
    <div className="page">
      <PageHeader
        title="Scores"
        description="How answers were rated, by thumbs, quality scores or evaluators. The last 30 days."
      />
      <div className="composer__row">
        <label className="inline-control" htmlFor={ids.by}>
          Group by
          <select
            id={ids.by}
            value={groupBy}
            onChange={(e) => setGroupBy(e.target.value)}
          >
            {GROUPS.map((g) => (
              <option key={g.value} value={g.value}>
                {g.label}
              </option>
            ))}
          </select>
        </label>
        <label className="inline-control" htmlFor={ids.name}>
          Only the score named
          <input
            id={ids.name}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. thumbs"
            maxLength={100}
          />
        </label>
      </div>
      <DataTable
        caption="Score summary"
        columns={groupColumns}
        rows={summary.data?.groups}
        getRowId={(g) => g.group}
        isLoading={summary.isLoading}
        error={
          summary.isError
            ? {
                title: "Could not load the summary",
                detail: errorMessage(summary.error),
                onRetry: () => void summary.refetch(),
              }
            : null
        }
        empty={{
          title: "No scores",
          detail:
            "Scores appear when applications send feedback to POST /v1/feedback or an evaluator runs.",
        }}
      />
      {isAdmin ? (
        <>
          <h2>Recent scores</h2>
          <DataTable
            caption="Recent scores"
            columns={scoreColumns}
            rows={recent.data}
            getRowId={(s) => s.id}
            isLoading={recent.isLoading}
            error={
              recent.isError
                ? {
                    title: "Could not load scores",
                    detail: errorMessage(recent.error),
                    onRetry: () => void recent.refetch(),
                  }
                : null
            }
            empty={{ title: "No scores", detail: "Nothing matches." }}
          />
        </>
      ) : null}
    </div>
  );
}
