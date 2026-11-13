import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../components/ui/ConfirmDialog";
import { ScoresPage } from "../evaluation/ScoresPage";
import { AnalyticsQueryPage, buildSpec } from "./AnalyticsQueryPage";
import { BatchJobsPage, runningAnnouncement } from "./BatchJobsPage";
import { PolicyPluginsPage, toBase64 } from "./PolicyPluginsPage";

const auth = vi.hoisted(() => ({ role: "admin" }));
vi.mock("../../state/AuthContext", () => ({
  useAuth: () => ({ token: "tok", user: { role: auth.role } }),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), del: vi.fn() },
}));

import { toast } from "sonner";
import { apiClient } from "../../api/client";

const get = vi.mocked(apiClient.get);
const post = vi.mocked(apiClient.post);
const patch = vi.mocked(apiClient.patch);
const del = vi.mocked(apiClient.del);

function renderIt(node: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ConfirmProvider>{node}</ConfirmProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  auth.role = "admin";
  [get, post, patch, del].forEach((m) => m.mockReset());
  vi.mocked(toast.error).mockReset();
});
afterEach(cleanup);

const PLUGIN = {
  id: "p1",
  name: "no-x",
  sha256: "a".repeat(64),
  size_bytes: 120,
  enabled: true,
  created_at: "2026-11-01T10:00:00Z",
};

describe("policy plugins", () => {
  it("lists plugins with their hash and state, and refuses anyone who is not an admin", async () => {
    get.mockResolvedValue([PLUGIN]);
    renderIt(<PolicyPluginsPage />);
    expect(await screen.findByText("no-x")).toBeTruthy();
    expect(screen.getByText("Enabled")).toBeTruthy();
    cleanup();
    auth.role = "developer";
    renderIt(<PolicyPluginsPage />);
    expect(screen.getByText(/need admin privileges/)).toBeTruthy();
  });

  it("uploads a file as base64 under the chosen name", async () => {
    get.mockResolvedValue([]);
    post.mockResolvedValue(PLUGIN);
    renderIt(<PolicyPluginsPage />);
    fireEvent.change(await screen.findByLabelText("Name"), {
      target: { value: "no-x" },
    });
    const file = new File([new Uint8Array([0, 97, 115, 109])], "p.wasm", {
      type: "application/wasm",
    });
    fireEvent.change(screen.getByLabelText("WebAssembly file"), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole("button", { name: /Upload plugin/ }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        "/api/v1/policy-plugins",
        { name: "no-x", module_b64: "AGFzbQ==" },
        "tok",
      ),
    );
  });

  it("refuses a bad name or a missing file without calling the server", async () => {
    get.mockResolvedValue([]);
    renderIt(<PolicyPluginsPage />);
    fireEvent.change(await screen.findByLabelText("Name"), {
      target: { value: "Bad Name" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Upload plugin/ }));
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "good-name" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Upload plugin/ }));
    expect(post).not.toHaveBeenCalled();
    expect(vi.mocked(toast.error)).toHaveBeenCalledTimes(2);
  });

  it("disables a plugin and deletes one after confirming", async () => {
    get.mockResolvedValue([PLUGIN]);
    patch.mockResolvedValue({ ...PLUGIN, enabled: false });
    del.mockResolvedValue(undefined as never);
    renderIt(<PolicyPluginsPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Disable" }));
    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith(
        "/api/v1/policy-plugins/p1",
        { enabled: false },
        "tok",
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Delete plugin no-x" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "Delete plugin" }),
    );
    await waitFor(() =>
      expect(del).toHaveBeenCalledWith("/api/v1/policy-plugins/p1", "tok"),
    );
  });

  it("encodes bytes beyond one chunk correctly", () => {
    const big = new Uint8Array(70_000).fill(65).buffer;
    expect(atob(toBase64(big)).length).toBe(70_000);
  });
});

describe("analytics query", () => {
  const CATALOG = {
    views: [
      {
        name: "requests",
        columns: {
          model: "text",
          cost_usd: "number",
          status_code: "int",
          created_at: "time",
        },
      },
      { name: "scores", columns: { score_name: "text", value: "number" } },
    ],
    aggregates: ["count", "sum", "avg", "min", "max", "p50", "p95"],
    operators: ["=", "!=", ">", ">=", "<", "<=", "in"],
  };

  it("builds a spec from the choices: group, measures and a typed filter", () => {
    const spec = buildSpec({
      view: "requests",
      group: "model",
      aggs: [
        { agg: "count", column: "" },
        { agg: "sum", column: "cost_usd" },
      ],
      filterColumn: "status_code",
      filterOp: "in",
      filterValue: "200, 500",
      limit: 10,
      kinds: { status_code: "int" },
    });
    expect(spec).toEqual({
      view: "requests",
      select: ["model", { agg: "count" }, { agg: "sum", column: "cost_usd" }],
      group_by: ["model"],
      where: [{ column: "status_code", op: "in", value: [200, 500] }],
      limit: 10,
    });
  });

  it("leaves out an empty filter and the grouping when none is chosen", () => {
    expect(
      buildSpec({
        view: "scores",
        group: "",
        aggs: [{ agg: "count", column: "" }],
        filterColumn: "",
        filterOp: "=",
        filterValue: "",
        limit: 5,
        kinds: {},
      }),
    ).toEqual({ view: "scores", select: [{ agg: "count" }], limit: 5 });
  });

  it("runs the query and shows the rows, saying when the limit was reached", async () => {
    get.mockResolvedValue(CATALOG);
    post.mockResolvedValue({
      columns: ["model", "count"],
      rows: [["openai/gpt-4o", 4]],
      row_count: 1,
      truncated: true,
    });
    renderIt(<AnalyticsQueryPage />);
    await screen.findByRole("option", { name: "Requests" });
    fireEvent.click(screen.getByRole("button", { name: /Run query/ }));
    expect(await screen.findByText("openai/gpt-4o")).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain(
      "the limit was reached",
    );
    expect(post.mock.calls[0][1]).toMatchObject({
      view: "requests",
      select: ["model", { agg: "count" }],
      group_by: ["model"],
    });
  });

  it("asks for a column when an aggregate other than count has none", async () => {
    get.mockResolvedValue(CATALOG);
    renderIt(<AnalyticsQueryPage />);
    await screen.findByRole("option", { name: "Requests" });
    fireEvent.change(screen.getByLabelText("Measure 1"), {
      target: { value: "sum" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Run query/ }));
    expect(post).not.toHaveBeenCalled();
    expect(vi.mocked(toast.error)).toHaveBeenCalled();
  });

  it("only offers numeric columns to sum", async () => {
    get.mockResolvedValue(CATALOG);
    renderIt(<AnalyticsQueryPage />);
    await screen.findByRole("option", { name: "Requests" });
    fireEvent.change(screen.getByLabelText("Measure 1"), {
      target: { value: "sum" },
    });
    const select = screen.getByLabelText("Of column") as HTMLSelectElement;
    expect(
      Array.from(select.options)
        .map((o) => o.value)
        .filter(Boolean)
        .sort(),
    ).toEqual(["cost_usd", "status_code"]);
  });
});

describe("scores", () => {
  const SUMMARY = {
    group_by: "score_name",
    groups: [{ group: "thumbs", count: 3, mean: 0.67, min: 0, max: 1 }],
  };
  const ITEMS = [
    {
      id: "s1",
      request_id: "r1",
      score_name: "thumbs",
      value: 1,
      source: "api",
      comment: "loved it",
      model: "openai/gpt-4o",
      created_at: "2026-11-01T10:00:00Z",
    },
  ];

  it("shows the summary and, for an admin, the individual scores with comments", async () => {
    get.mockImplementation(async (path: string) =>
      path.startsWith("/api/v1/scores/summary") ? SUMMARY : ITEMS,
    );
    renderIt(<ScoresPage />);
    expect(await screen.findByText("0.67")).toBeTruthy();
    expect(await screen.findByText("loved it")).toBeTruthy();
  });

  it("gives a developer the summary only, never the individual scores or comments", async () => {
    auth.role = "developer";
    get.mockImplementation(async (path: string) => {
      if (path.startsWith("/api/v1/scores/summary")) return SUMMARY;
      throw new Error(`a developer must not fetch ${path}`);
    });
    renderIt(<ScoresPage />);
    expect(await screen.findByText("0.67")).toBeTruthy();
    expect(screen.queryByText("Recent scores")).toBeNull();
  });

  it("passes the grouping and the name filter to the server", async () => {
    get.mockResolvedValue(SUMMARY);
    renderIt(<ScoresPage />);
    await screen.findByText("thumbs");
    fireEvent.change(screen.getByLabelText("Group by"), {
      target: { value: "model" },
    });
    fireEvent.change(screen.getByLabelText("Only the score named"), {
      target: { value: "quality" },
    });
    await waitFor(() =>
      expect(get).toHaveBeenCalledWith(
        "/api/v1/scores/summary?group_by=model&score_name=quality",
        "tok",
      ),
    );
  });

  it("refuses a viewer", () => {
    auth.role = "viewer";
    renderIt(<ScoresPage />);
    expect(screen.getByText(/need developer or admin/)).toBeTruthy();
    expect(get).not.toHaveBeenCalled();
  });
});

const JOB = {
  id: "b1",
  status: "in_progress",
  created_by: "ana@example.com",
  total: 40,
  completed: 12,
  failed: 1,
  cost_usd: 0.31,
  max_cost_usd: 5,
  error: null,
  created_at: "2026-11-02T09:00:00Z",
  finished_at: null,
};

describe("batch jobs", () => {
  it("shows progress and cost for each job, and refuses anyone who is not an admin", async () => {
    get.mockResolvedValue([JOB, { ...JOB, id: "b2", status: "budget_exceeded", completed: 60, failed: 0, total: 100, error: "The spending cap was reached." }]);
    renderIt(<BatchJobsPage />);
    expect(await screen.findByText("13 / 40 (1 failed)")).toBeTruthy();
    const bar = screen.getAllByRole("progressbar")[0];
    expect(bar.getAttribute("aria-valuenow")).toBe("13");
    expect(bar.getAttribute("aria-valuemax")).toBe("40");
    expect(bar.getAttribute("aria-valuetext")).toBe("13 of 40 lines, 1 failed");
    expect(screen.getByText("Running")).toBeTruthy();
    expect(screen.getByText("Stopped at the cap")).toBeTruthy();
    expect(screen.getByText("The spending cap was reached.")).toBeTruthy();
    cleanup();
    auth.role = "developer";
    renderIt(<BatchJobsPage />);
    expect(screen.getByText(/need admin privileges/)).toBeTruthy();
    expect(get).toHaveBeenCalledTimes(1);
  });

  it("offers Cancel only on a job that is still active, and asks first", async () => {
    get.mockResolvedValue([JOB, { ...JOB, id: "b2", status: "completed" }]);
    post.mockResolvedValue({ ...JOB, status: "cancelled" });
    renderIt(<BatchJobsPage />);
    const cancel = await screen.findByRole("button", { name: /Cancel/ });
    expect(screen.getAllByRole("button", { name: /Cancel/ })).toHaveLength(1);
    fireEvent.click(cancel);
    fireEvent.click(await screen.findByRole("button", { name: "Cancel job" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/api/v1/batch-jobs/b1/cancel", {}, "tok"));
  });

  it("does not cancel when the confirmation is dismissed", async () => {
    get.mockResolvedValue([JOB]);
    renderIt(<BatchJobsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /Cancel/ }));
    fireEvent.click(await screen.findByRole("button", { name: /Keep|Close|No|Dismiss|Back/i }));
    expect(post).not.toHaveBeenCalled();
  });
});

describe("runningAnnouncement", () => {
  it("says how many jobs run, in one sentence, and when none do", () => {
    const job = (status: string) => ({ ...JOB, status }) as never;
    expect(runningAnnouncement(undefined)).toBe("No batch jobs are running.");
    expect(runningAnnouncement([job("completed")])).toBe("No batch jobs are running.");
    expect(runningAnnouncement([job("in_progress")])).toBe("1 batch job is running.");
    expect(runningAnnouncement([job("validating"), job("in_progress"), job("failed")])).toBe("2 batch jobs are running.");
  });
});
