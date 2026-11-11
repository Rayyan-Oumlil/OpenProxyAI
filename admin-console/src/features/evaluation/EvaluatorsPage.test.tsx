import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Evaluator } from "../../api/evaluationTypes";
import { ConfirmProvider } from "../../components/ui/ConfirmDialog";
import { describeConfig, EvaluatorsPage } from "./EvaluatorsPage";

const auth = vi.hoisted(() => ({ role: "admin" }));
vi.mock("../../state/AuthContext", () => ({ useAuth: () => ({ token: "tok", user: { role: auth.role } }) }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("../../api/client", () => ({ apiClient: { get: vi.fn(), post: vi.fn(), del: vi.fn() } }));

import { toast } from "sonner";
import { apiClient } from "../../api/client";

const get = vi.mocked(apiClient.get);
const post = vi.mocked(apiClient.post);
const del = vi.mocked(apiClient.del);

const EVALUATORS: Evaluator[] = [
  { id: "e1", name: "exact-match", type: "exact", config: { case_sensitive: false, strip: true }, created_at: "2026-11-01T10:00:00Z" },
  { id: "e2", name: "digits", type: "regex", config: { pattern: "^\\d+$", mode: "fullmatch", ignore_case: false }, created_at: "2026-11-01T10:00:00Z" },
  { id: "e3", name: "helpful", type: "llm_judge", config: { model: "openai/gpt-4o-mini", criteria: "c", scale: "1-5", pass_threshold: 4 }, created_at: "2026-11-01T10:00:00Z" },
];

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ConfirmProvider>
        <EvaluatorsPage />
      </ConfirmProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset().mockResolvedValue(EVALUATORS);
  post.mockReset();
  del.mockReset();
  vi.mocked(toast.error).mockReset();
  auth.role = "admin";
});
afterEach(cleanup);

describe("describeConfig", () => {
  it("says in one line what each kind does", () => {
    expect(describeConfig(EVALUATORS[0])).toBe("ignores case, ignores surrounding whitespace");
    expect(describeConfig(EVALUATORS[1])).toBe("must match fully /^\\d+$/");
    expect(describeConfig(EVALUATORS[2])).toBe("openai/gpt-4o-mini, 1 to 5, passes at 4");
    expect(describeConfig({ type: "llm_judge", config: { model: "m/x", scale: "pass_fail" } })).toBe("m/x, pass or fail");
  });
});

describe("EvaluatorsPage", () => {
  it("lists evaluators with their type and settings", async () => {
    renderPage();
    expect(await screen.findByText("exact-match")).toBeTruthy();
    expect(screen.getByText("LLM judge")).toBeTruthy();
    expect(screen.getByText("openai/gpt-4o-mini, 1 to 5, passes at 4")).toBeTruthy();
  });

  it("is admin only", () => {
    auth.role = "viewer";
    renderPage();
    expect(screen.getByText(/You need admin privileges/)).toBeTruthy();
    expect(get).not.toHaveBeenCalled();
  });

  it("creates an exact-match evaluator", async () => {
    post.mockResolvedValue(EVALUATORS[0]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /New evaluator/ }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "strict" } });
    fireEvent.click(screen.getByLabelText("Case-sensitive"));
    fireEvent.click(screen.getByRole("button", { name: "Create evaluator" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/api/v1/evaluators", { name: "strict", type: "exact", config: { case_sensitive: true } }, "tok"));
  });

  it("shows the fields of the chosen type and sends a regex evaluator", async () => {
    post.mockResolvedValue(EVALUATORS[1]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /New evaluator/ }));
    expect(screen.queryByLabelText(/Pattern/)).toBeNull();
    fireEvent.change(screen.getByLabelText("Type"), { target: { value: "regex" } });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "greeting" } });
    fireEvent.change(screen.getByLabelText(/Pattern/), { target: { value: "^Bonjour" } });
    fireEvent.change(screen.getByLabelText("Match"), { target: { value: "fullmatch" } });
    fireEvent.click(screen.getByRole("button", { name: "Create evaluator" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/api/v1/evaluators", { name: "greeting", type: "regex", config: { pattern: "^Bonjour", mode: "fullmatch", ignore_case: false } }, "tok"),
    );
  });

  it("sends a judge with its criteria, and the pass threshold only on the 1 to 5 scale", async () => {
    post.mockResolvedValue(EVALUATORS[2]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /New evaluator/ }));
    fireEvent.change(screen.getByLabelText("Type"), { target: { value: "llm_judge" } });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "helpful" } });
    fireEvent.change(screen.getByLabelText("Judge model"), { target: { value: "openai/gpt-4o-mini" } });
    fireEvent.change(screen.getByLabelText(/Criteria/), { target: { value: "Is it helpful?" } });
    fireEvent.change(screen.getByLabelText("Passes at"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Create evaluator" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        "/api/v1/evaluators",
        { name: "helpful", type: "llm_judge", config: { model: "openai/gpt-4o-mini", criteria: "Is it helpful?", scale: "1-5", pass_threshold: 3 } },
        "tok",
      ),
    );
    post.mockClear();
    fireEvent.click(screen.getByRole("button", { name: /New evaluator/ }));
  });

  it("shows the server's explanation when a config is refused", async () => {
    post.mockRejectedValue(new Error("pattern is not a valid regular expression: missing )"));
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /New evaluator/ }));
    fireEvent.change(screen.getByLabelText("Type"), { target: { value: "regex" } });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "bad" } });
    fireEvent.change(screen.getByLabelText(/Pattern/), { target: { value: "(" } });
    fireEvent.click(screen.getByRole("button", { name: "Create evaluator" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("pattern is not a valid regular expression: missing )"));
  });

  it("will not create an evaluator without a name", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /New evaluator/ }));
    fireEvent.click(screen.getByRole("button", { name: "Create evaluator" }));
    expect(toast.error).toHaveBeenCalledWith("Give the evaluator a name.");
    expect(post).not.toHaveBeenCalled();
  });

  it("deletes after confirmation", async () => {
    del.mockResolvedValue(undefined);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Delete evaluator exact-match" }));
    expect(del).not.toHaveBeenCalled();
    fireEvent.click(await screen.findByRole("button", { name: "Delete evaluator" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("/api/v1/evaluators/e1", "tok"));
  });
});
