import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Dataset, DatasetItem } from "../../api/evaluationTypes";
import { ConfirmProvider } from "../../components/ui/ConfirmDialog";
import { DatasetsPage } from "./DatasetsPage";

const auth = vi.hoisted(() => ({ role: "admin" }));
vi.mock("../../state/AuthContext", () => ({ useAuth: () => ({ token: "tok", user: { role: auth.role } }) }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("../../api/client", () => ({ apiClient: { get: vi.fn(), post: vi.fn(), del: vi.fn() } }));

import { toast } from "sonner";
import { apiClient } from "../../api/client";

const get = vi.mocked(apiClient.get);
const post = vi.mocked(apiClient.post);
const del = vi.mocked(apiClient.del);

const DATASET: Dataset = { id: "d1", name: "support", description: "Support tickets", item_count: 2, created_at: "2026-11-01T10:00:00Z" };
const ITEMS: DatasetItem[] = [
  { id: "i1", request_id: "r1", messages: [{ role: "user", content: "How do I reset my password?" }], output: "Click reset.", expected: null, created_at: "2026-11-01T10:00:00Z" },
  { id: "i2", request_id: null, messages: [{ role: "user", content: "What is 2+2?" }], output: null, expected: "4", created_at: "2026-11-01T10:00:00Z" },
];

function mockApi(datasets: Dataset[] = [DATASET]) {
  get.mockImplementation(async (path: string) => {
    if (path === "/api/v1/datasets") return datasets;
    if (path.startsWith("/api/v1/datasets/d1/items")) return ITEMS;
    throw new Error(`unmocked ${path}`);
  });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ConfirmProvider>
        <DatasetsPage />
      </ConfirmProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  del.mockReset();
  vi.mocked(toast.error).mockReset();
  auth.role = "admin";
});
afterEach(cleanup);

describe("DatasetsPage", () => {
  it("lists datasets with their item counts", async () => {
    mockApi();
    renderPage();
    expect(await screen.findByText("support")).toBeTruthy();
    expect(screen.getByText("Support tickets")).toBeTruthy();
  });

  it("says so when there are none, and points at the policy page for capturing", async () => {
    mockApi([]);
    renderPage();
    expect(await screen.findByText("No datasets")).toBeTruthy();
    expect(screen.getByText(/Capturing is off until you set a sample rate/)).toBeTruthy();
  });

  it("is admin only: a non-admin gets a notice and no request is made", async () => {
    auth.role = "developer";
    mockApi();
    renderPage();
    expect(screen.getByText(/You need admin privileges/)).toBeTruthy();
    expect(get).not.toHaveBeenCalled();
  });

  it("opens a dataset to show its items, marking captured and written ones", async () => {
    mockApi();
    renderPage();
    fireEvent.click(await screen.findByText("support"));
    expect(await screen.findByText("How do I reset my password?")).toBeTruthy();
    expect(screen.getByText("Captured")).toBeTruthy();
    expect(screen.getByText("Written")).toBeTruthy();
    expect(screen.getByText("4")).toBeTruthy(); // the expected answer
  });

  it("creates a dataset and opens it", async () => {
    mockApi([]);
    post.mockResolvedValue({ ...DATASET, id: "d1", item_count: 0 });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /New dataset/ }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "support" } });
    fireEvent.click(screen.getByRole("button", { name: "Create dataset" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/api/v1/datasets", { name: "support" }, "tok"));
  });

  it("refuses an empty name before calling the server", async () => {
    mockApi([]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /New dataset/ }));
    fireEvent.click(screen.getByRole("button", { name: "Create dataset" }));
    expect(toast.error).toHaveBeenCalledWith("Give the dataset a name.");
    expect(post).not.toHaveBeenCalled();
  });

  it("adds an item by hand with its expected answer", async () => {
    mockApi();
    post.mockResolvedValue(ITEMS[1]);
    renderPage();
    fireEvent.click(await screen.findByText("support"));
    const form = await screen.findByRole("form", { name: "Add an item to support" });
    fireEvent.change(within(form).getByLabelText("Prompt"), { target: { value: "Capital of France?" } });
    fireEvent.change(within(form).getByLabelText(/Expected answer/), { target: { value: "Paris" } });
    fireEvent.click(within(form).getByRole("button", { name: "Add item" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/api/v1/datasets/d1/items", { messages: [{ role: "user", content: "Capital of France?" }], expected: "Paris" }, "tok"),
    );
  });

  it("does not wipe the next item the user has started typing while the previous one is still saving", async () => {
    mockApi();
    let finish: (item: DatasetItem) => void = () => {};
    post.mockReturnValue(new Promise<DatasetItem>((resolve) => (finish = resolve)));
    renderPage();
    fireEvent.click(await screen.findByText("support"));
    const form = await screen.findByRole("form", { name: "Add an item to support" });
    const prompt = within(form).getByLabelText("Prompt") as HTMLTextAreaElement;
    fireEvent.change(prompt, { target: { value: "first" } });
    fireEvent.click(within(form).getByRole("button", { name: "Add item" }));
    fireEvent.change(prompt, { target: { value: "second, typed while the first saves" } });
    finish(ITEMS[1]);
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    await new Promise((r) => setTimeout(r, 20));
    expect(prompt.value).toBe("second, typed while the first saves");
  });

  it("clears the fields once an item is saved and nothing else was typed", async () => {
    mockApi();
    post.mockResolvedValue(ITEMS[1]);
    renderPage();
    fireEvent.click(await screen.findByText("support"));
    const form = await screen.findByRole("form", { name: "Add an item to support" });
    const prompt = within(form).getByLabelText("Prompt") as HTMLTextAreaElement;
    fireEvent.change(prompt, { target: { value: "only one" } });
    fireEvent.click(within(form).getByRole("button", { name: "Add item" }));
    await waitFor(() => expect(prompt.value).toBe(""));
  });

  it("shows the server's reason when an item is refused, for example personal data", async () => {
    mockApi();
    post.mockRejectedValue(new Error("This item contains personal data (ssn)."));
    renderPage();
    fireEvent.click(await screen.findByText("support"));
    const form = await screen.findByRole("form", { name: "Add an item to support" });
    fireEvent.change(within(form).getByLabelText("Prompt"), { target: { value: "my ssn is 123-45-6789" } });
    fireEvent.click(within(form).getByRole("button", { name: "Add item" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("This item contains personal data (ssn)."));
  });

  it("imports with filters and reports what was skipped", async () => {
    mockApi();
    post.mockResolvedValue({ imported: 7, skipped_redacted: 3, skipped_duplicate: 1, stopped_at_capacity: false });
    renderPage();
    fireEvent.click(await screen.findByText("support"));
    fireEvent.click(await screen.findByRole("button", { name: /Import from traffic/ }));
    fireEvent.change(screen.getByLabelText(/Feedback score/), { target: { value: "thumbs" } });
    fireEvent.change(screen.getByLabelText("At least"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("Model (optional)"), { target: { value: "openai/gpt-4o-mini" } });
    fireEvent.click(screen.getByRole("button", { name: "Import" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        "/api/v1/datasets/d1/import",
        { limit: 100, order: "latest", model: "openai/gpt-4o-mini", score_name: "thumbs", min_score: 1 },
        "tok",
      ),
    );
    expect(await screen.findByText(/Skipped 3 with personal data and 1 already in this dataset/)).toBeTruthy();
  });

  it("will not send a score range without a score name", async () => {
    mockApi();
    renderPage();
    fireEvent.click(await screen.findByText("support"));
    fireEvent.click(await screen.findByRole("button", { name: /Import from traffic/ }));
    fireEvent.change(screen.getByLabelText("At least"), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Import" }));
    expect(toast.error).toHaveBeenCalledWith("A score range needs a score name, for example thumbs.");
    expect(post).not.toHaveBeenCalled();
  });

  it("deletes a dataset only after the confirmation dialog", async () => {
    mockApi();
    del.mockResolvedValue(undefined);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Delete dataset support" }));
    expect(del).not.toHaveBeenCalled();
    fireEvent.click(await screen.findByRole("button", { name: "Delete dataset" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("/api/v1/datasets/d1", "tok"));
  });

  it("shows an error state with a retry when the list cannot load", async () => {
    get.mockRejectedValue(new Error("boom"));
    renderPage();
    expect(await screen.findByText("Unable to load datasets")).toBeTruthy();
  });
});
