import { useId, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import { PageHeader } from "../../components/ui/PageHeader";
import { useAuth } from "../../state/AuthContext";

const BASE = "/api/v1/analytics/query";
const NUMERIC = ["int", "number"];

type Catalog = {
  views: { name: string; columns: Record<string, string> }[];
  aggregates: string[];
  operators: string[];
};
type Result = {
  columns: string[];
  rows: unknown[][];
  row_count: number;
  truncated: boolean;
};
type Agg = { agg: string; column: string };

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "The query failed.";
}

/** What the form builds. Kept separate so it can be tested without rendering. */
export function buildSpec(input: {
  view: string;
  group: string;
  aggs: Agg[];
  filterColumn: string;
  filterOp: string;
  filterValue: string;
  limit: number;
  kinds: Record<string, string>;
}) {
  const select: unknown[] = [];
  if (input.group) select.push(input.group);
  for (const a of input.aggs)
    select.push(
      a.agg === "count" && !a.column
        ? { agg: "count" }
        : { agg: a.agg, column: a.column },
    );
  const where: unknown[] = [];
  if (input.filterColumn && input.filterValue.trim() !== "") {
    const kind = input.kinds[input.filterColumn];
    const raw = input.filterValue.trim();
    const one = (v: string) => (NUMERIC.includes(kind) ? Number(v) : v);
    where.push({
      column: input.filterColumn,
      op: input.filterOp,
      value:
        input.filterOp === "in"
          ? raw.split(",").map((v) => one(v.trim()))
          : one(raw),
    });
  }
  return {
    view: input.view,
    select,
    ...(input.group ? { group_by: [input.group] } : {}),
    ...(where.length ? { where } : {}),
    limit: input.limit,
  };
}

export function AnalyticsQueryPage() {
  const { token, user } = useAuth();
  const ids = {
    view: useId(),
    group: useId(),
    agg: useId(),
    aggCol: useId(),
    fCol: useId(),
    fOp: useId(),
    fVal: useId(),
    limit: useId(),
  };
  const isAdmin = user?.role === "admin";
  const [view, setView] = useState("requests");
  const [group, setGroup] = useState("model");
  const [aggs, setAggs] = useState<Agg[]>([{ agg: "count", column: "" }]);
  const [filterColumn, setFilterColumn] = useState("");
  const [filterOp, setFilterOp] = useState("=");
  const [filterValue, setFilterValue] = useState("");
  const [limit, setLimit] = useState(100);

  const catalog = useQuery({
    queryKey: ["analytics-catalog", token],
    queryFn: () => apiClient.get<Catalog>(`${BASE}/catalog`, token!),
    enabled: Boolean(token) && isAdmin,
  });
  const run = useMutation({
    mutationFn: (spec: unknown) => apiClient.post<Result>(BASE, spec, token!),
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (!isAdmin) return <p>You need admin privileges to query analytics.</p>;
  const columns =
    catalog.data?.views.find((v) => v.name === view)?.columns ?? {};
  const names = Object.keys(columns).sort();
  const numeric = names.filter((n) => NUMERIC.includes(columns[n]));
  const aggColumns = (agg: string) =>
    agg === "count"
      ? names
      : agg === "min" || agg === "max"
        ? names.filter((n) => [...NUMERIC, "time"].includes(columns[n]))
        : numeric;

  return (
    <div className="page">
      <PageHeader
        title="Analytics query"
        description="Ask your own request log and scores questions. Read-only, limited to your organization, and every query is audited."
      />
      <form
        className="stack-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (aggs.some((a) => a.agg !== "count" && !a.column))
            return toast.error("Choose a column for each aggregate.");
          run.mutate(
            buildSpec({
              view,
              group,
              aggs,
              filterColumn,
              filterOp,
              filterValue,
              limit,
              kinds: columns,
            }),
          );
        }}
      >
        <div className="composer__row">
          <label className="inline-control" htmlFor={ids.view}>
            Data
            <select
              id={ids.view}
              value={view}
              onChange={(e) => {
                setView(e.target.value);
                setGroup("");
                setFilterColumn("");
                setAggs([{ agg: "count", column: "" }]);
              }}
            >
              {(catalog.data?.views ?? []).map((v) => (
                <option key={v.name} value={v.name}>
                  {v.name === "requests" ? "Requests" : "Scores"}
                </option>
              ))}
            </select>
          </label>
          <label className="inline-control" htmlFor={ids.group}>
            Group by
            <select
              id={ids.group}
              value={group}
              onChange={(e) => setGroup(e.target.value)}
            >
              <option value="">Nothing (one row)</option>
              {names.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label className="inline-control" htmlFor={ids.limit}>
            Rows (up to 1000)
            <input
              id={ids.limit}
              type="number"
              min={1}
              max={1000}
              value={limit}
              onChange={(e) =>
                setLimit(
                  Math.max(1, Math.min(1000, Number(e.target.value) || 1)),
                )
              }
            />
          </label>
        </div>
        <fieldset className="inline-control" style={{ border: 0, padding: 0 }}>
          <legend>Measures</legend>
          {aggs.map((a, i) => (
            <div key={i} className="composer__row">
              <label className="inline-control" htmlFor={`${ids.agg}-${i}`}>
                Measure {i + 1}
                <select
                  id={`${ids.agg}-${i}`}
                  value={a.agg}
                  onChange={(e) =>
                    setAggs(
                      aggs.map((x, j) =>
                        j === i ? { agg: e.target.value, column: "" } : x,
                      ),
                    )
                  }
                >
                  {(catalog.data?.aggregates ?? ["count"]).map((g) => (
                    <option key={g} value={g}>
                      {g}
                    </option>
                  ))}
                </select>
              </label>
              <label className="inline-control" htmlFor={`${ids.aggCol}-${i}`}>
                Of column
                <select
                  id={`${ids.aggCol}-${i}`}
                  value={a.column}
                  onChange={(e) =>
                    setAggs(
                      aggs.map((x, j) =>
                        j === i ? { ...x, column: e.target.value } : x,
                      ),
                    )
                  }
                >
                  <option value="">
                    {a.agg === "count" ? "Rows" : "Choose…"}
                  </option>
                  {aggColumns(a.agg).map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          ))}
          <div className="flex gap-2">
            <button
              type="button"
              className="btn-outline btn-small"
              onClick={() => setAggs([...aggs, { agg: "count", column: "" }])}
              disabled={aggs.length >= 6}
            >
              Add a measure
            </button>
            {aggs.length > 1 ? (
              <button
                type="button"
                className="btn-outline btn-small"
                onClick={() => setAggs(aggs.slice(0, -1))}
              >
                Remove last
              </button>
            ) : null}
          </div>
        </fieldset>
        <div className="composer__row">
          <label className="inline-control" htmlFor={ids.fCol}>
            Filter column
            <select
              id={ids.fCol}
              value={filterColumn}
              onChange={(e) => setFilterColumn(e.target.value)}
            >
              <option value="">No filter</option>
              {names.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label className="inline-control" htmlFor={ids.fOp}>
            Operator
            <select
              id={ids.fOp}
              value={filterOp}
              onChange={(e) => setFilterOp(e.target.value)}
            >
              {(catalog.data?.operators ?? ["="]).map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          </label>
          <label className="inline-control" htmlFor={ids.fVal}>
            Value {filterOp === "in" ? "(comma separated)" : ""}
            <input
              id={ids.fVal}
              value={filterValue}
              onChange={(e) => setFilterValue(e.target.value)}
            />
          </label>
        </div>
        <div>
          <button
            type="submit"
            className="bg-accent-sky"
            disabled={run.isPending || !catalog.data}
          >
            <Play size={14} aria-hidden="true" />{" "}
            {run.isPending ? "Running…" : "Run query"}
          </button>
        </div>
      </form>
      {run.data ? (
        <section aria-label="Query result">
          <p className="text-muted text-sm" role="status">
            {run.data.row_count} {run.data.row_count === 1 ? "row" : "rows"}
            {run.data.truncated
              ? ", the limit was reached so there may be more"
              : ""}
            . The last 30 days unless you narrow it.
          </p>
          <div style={{ overflowX: "auto" }}>
            <table className="dt">
              <caption className="sr-only">Query result</caption>
              <thead>
                <tr>
                  {run.data.columns.map((c) => (
                    <th key={c} scope="col">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {run.data.rows.map((row, i) => (
                  <tr key={i}>
                    {row.map((cell, j) => (
                      <td key={j}>{String(cell ?? "—")}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}
