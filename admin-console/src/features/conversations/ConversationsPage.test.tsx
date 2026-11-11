import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  Conversation,
  ContextSummary,
  Turn,
  TurnExchange,
} from "../../api/conversationTypes";
import { ConfirmProvider } from "../../components/ui/ConfirmDialog";
import { ConversationsPage } from "./ConversationsPage";

const auth = vi.hoisted(() => ({ role: "developer" }));
vi.mock("../../state/AuthContext", () => ({
  useAuth: () => ({ token: "tok", user: { role: auth.role } }),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), del: vi.fn() },
}));

import { apiClient } from "../../api/client";

const get = vi.mocked(apiClient.get);
const post = vi.mocked(apiClient.post);
const del = vi.mocked(apiClient.del);

const CONVERSATION: Conversation = {
  id: "c1",
  title: "Q3 review",
  visibility: "private",
  team_id: null,
  tags: ["finance"],
  system_prompt: null,
  owner_id: "u1",
  owner_email: "me@x.test",
  is_owner: true,
  turn_count: 2,
  created_at: "2026-11-01T10:00:00Z",
  updated_at: "2026-11-01T10:00:00Z",
};
const TURNS: Turn[] = [
  {
    id: "t1",
    seq: 1,
    role: "user",
    content: "Project Falcon price?",
    data_class: "confidential",
    model: null,
    created_at: "2026-11-01T10:00:00Z",
  },
  {
    id: "t2",
    seq: 2,
    role: "assistant",
    content: "About 4.2 billion.",
    data_class: "confidential",
    model: "openai/gpt-4o",
    created_at: "2026-11-01T10:00:05Z",
  },
];
const MODELS = [
  { model_id: "openai/gpt-4o", max_data_class: "confidential" },
  { model_id: "anthropic/claude", max_data_class: "internal" },
];
const CONTEXT: ContextSummary = {
  package_id: "p1",
  model: "anthropic/claude",
  data_class: "internal",
  routing_mode: "enforce",
  included_turn_ids: [],
  withheld: [
    { turn_id: "t1", seq: 1, reason: "above_clearance" },
    { turn_id: "t2", seq: 2, reason: "above_clearance" },
  ],
  estimated_tokens: 12,
  payload_sha256: "a".repeat(64),
  outcome: "ok",
  created_at: "2026-11-01T10:01:00Z",
};

function mockApi(
  overrides: {
    conversation?: Conversation;
    list?: Conversation[];
    org?: Conversation[];
  } = {},
) {
  const conversation = overrides.conversation ?? CONVERSATION;
  get.mockImplementation(async (path: string) => {
    if (path === "/api/v1/conversations?scope=mine")
      return overrides.list ?? [CONVERSATION];
    if (path === "/api/v1/conversations?scope=shared") return [];
    if (path === "/api/v1/conversations?scope=org")
      return overrides.org ?? [CONVERSATION];
    if (path === "/api/v1/conversations/models") return MODELS;
    if (path === "/api/v1/conversations/teams")
      return [{ id: "team1", name: "Finance" }];
    if (path === "/api/v1/conversations/c1") return conversation;
    if (path === "/api/v1/conversations/c1/turns") return TURNS;
    if (path === "/api/v1/conversations/c1/turns/t2/context") return CONTEXT;
    throw new Error(`unmocked ${path}`);
  });
}

function renderAt(path: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ConfirmProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/conversations" element={<ConversationsPage />} />
            <Route path="/conversations/:id" element={<ConversationsPage />} />
          </Routes>
        </MemoryRouter>
      </ConfirmProvider>
    </QueryClientProvider>,
  );
}

const exchange = (context: ContextSummary): TurnExchange => ({
  user_turn: { ...TURNS[0], id: "t3", seq: 3 },
  assistant_turn: { ...TURNS[1], id: "t4", seq: 4 },
  context,
  prompt_tokens: 5,
  completion_tokens: 3,
  cost_usd: "0",
});

beforeEach(() => {
  auth.role = "developer";
  get.mockReset();
  post.mockReset();
  del.mockReset();
});
afterEach(cleanup);

describe("the conversation list", () => {
  it("lists your conversations and opens one", async () => {
    mockApi();
    renderAt("/conversations");
    const link = await screen.findByRole("link", { name: /Q3 review/ });
    expect(link.getAttribute("href")).toBe("/conversations/c1");
    expect(
      screen.queryByRole("button", { name: "Whole organization" }),
    ).toBeNull();
  });

  it("shows admins the whole-organization view as titles and sizes only, with no way to open a thread", async () => {
    auth.role = "admin";
    mockApi({
      org: [{ ...CONVERSATION, is_owner: false, owner_email: "alice@x.test" }],
    });
    renderAt("/conversations");
    fireEvent.click(
      await screen.findByRole("button", { name: "Whole organization" }),
    );
    expect(await screen.findByText(/alice@x.test/)).toBeTruthy();
    expect(screen.queryByRole("link", { name: /Q3 review/ })).toBeNull();
    expect(screen.getByText(/Messages stay with their owners/)).toBeTruthy();
  });

  it("starts a conversation, shared with a team when one is chosen", async () => {
    mockApi();
    post.mockResolvedValue({ ...CONVERSATION, id: "c9" });
    renderAt("/conversations");
    fireEvent.click(
      await screen.findByRole("button", { name: /New conversation/ }),
    );
    fireEvent.change(await screen.findByLabelText("Title"), {
      target: { value: "Launch" },
    });
    fireEvent.change(screen.getByLabelText(/Tags/), {
      target: { value: "ops, Q3 " },
    });
    await screen.findByRole("option", { name: "Team: Finance" });
    fireEvent.change(screen.getByLabelText("Share with"), {
      target: { value: "team1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Start conversation" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        "/api/v1/conversations",
        {
          title: "Launch",
          tags: ["ops", "Q3"],
          visibility: "team",
          team_id: "team1",
        },
        "tok",
      ),
    );
  });

  it("sends a standing instruction with the new conversation", async () => {
    mockApi();
    post.mockResolvedValue({ ...CONVERSATION, id: "c9" });
    renderAt("/conversations");
    fireEvent.click(
      await screen.findByRole("button", { name: /New conversation/ }),
    );
    fireEvent.change(await screen.findByLabelText("Title"), {
      target: { value: "Review" },
    });
    fireEvent.change(screen.getByLabelText(/Standing instruction/), {
      target: { value: "  Be terse.  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Start conversation" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        "/api/v1/conversations",
        { title: "Review", tags: [], system_prompt: "Be terse." },
        "tok",
      ),
    );
  });

  it("offers whole-organization sharing to admins only, and it replaces the team choice", async () => {
    mockApi();
    post.mockResolvedValue({ ...CONVERSATION, id: "c9" });
    renderAt("/conversations");
    fireEvent.click(
      await screen.findByRole("button", { name: /New conversation/ }),
    );
    await screen.findByLabelText("Title");
    expect(
      screen.queryByLabelText(/Share with the whole organization/),
    ).toBeNull();
    cleanup();
    auth.role = "admin";
    renderAt("/conversations");
    fireEvent.click(
      await screen.findByRole("button", { name: /New conversation/ }),
    );
    fireEvent.change(await screen.findByLabelText("Title"), {
      target: { value: "Handbook" },
    });
    fireEvent.click(screen.getByLabelText(/Share with the whole organization/));
    expect(
      (screen.getByLabelText("Share with") as HTMLSelectElement).disabled,
    ).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Start conversation" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        "/api/v1/conversations",
        { title: "Handbook", tags: [], visibility: "org" },
        "tok",
      ),
    );
  });

  it("says in the drawer what enforcement would have held back when routing is only in preview", async () => {
    mockApi();
    get.mockImplementation(async (path: string) => {
      if (path.endsWith("/context"))
        return {
          ...CONTEXT,
          routing_mode: "log_only",
          withheld: [],
          included_turn_ids: ["t1", "t2"],
          would_withhold: [
            { turn_id: "t1", seq: 1, reason: "above_clearance" },
          ],
        };
      if (path === "/api/v1/conversations/c1") return CONVERSATION;
      if (path === "/api/v1/conversations/c1/turns") return TURNS;
      if (path === "/api/v1/conversations/models") return MODELS;
      return [];
    });
    renderAt("/conversations/c1");
    const answer = await screen.findByRole("article", {
      name: "Assistant, message 2",
    });
    fireEvent.click(
      within(answer).getByRole("button", { name: "Context sent" }),
    );
    expect((await screen.findByRole("note")).textContent).toContain(
      "1 earlier message (#1) would have been held back",
    );
  });

  it("refuses an empty title without calling the server", async () => {
    mockApi();
    renderAt("/conversations");
    fireEvent.click(
      await screen.findByRole("button", { name: /New conversation/ }),
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Start conversation" }),
    );
    expect(post).not.toHaveBeenCalled();
  });
});

describe("a thread", () => {
  it("shows each message with its class and, for answers, which model wrote them", async () => {
    mockApi();
    renderAt("/conversations/c1");
    const answer = await screen.findByRole("article", {
      name: "Assistant, message 2",
    });
    expect(within(answer).getByText("openai/gpt-4o")).toBeTruthy();
    expect(within(answer).getByText("Confidential")).toBeTruthy();
    expect(
      screen.getByRole("article", { name: "You, message 1" }),
    ).toBeTruthy();
  });

  it("sends the chosen model and any asserted class, and tells the user what was held back", async () => {
    mockApi();
    post.mockResolvedValue(exchange(CONTEXT));
    renderAt("/conversations/c1");
    await screen.findByRole("option", {
      name: "anthropic/claude (up to Internal)",
    });
    fireEvent.change(screen.getByLabelText("Model"), {
      target: { value: "anthropic/claude" },
    });
    fireEvent.change(screen.getByLabelText("Sensitivity"), {
      target: { value: "confidential" },
    });
    fireEvent.change(screen.getByLabelText("Message"), {
      target: { value: "Summarise it" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Send/ }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        "/api/v1/conversations/c1/turns",
        {
          content: "Summarise it",
          model: "anthropic/claude",
          data_class: "confidential",
        },
        "tok",
      ),
    );
    const status = await screen.findByRole("status");
    await waitFor(() =>
      expect(status.textContent).toContain(
        "2 earlier messages were not sent to anthropic/claude: 2 more sensitive than anthropic/claude is cleared for.",
      ),
    );
    expect(
      (screen.getByLabelText("Message") as HTMLTextAreaElement).value,
    ).toBe("");
    expect(
      (screen.getByLabelText("Sensitivity") as HTMLSelectElement).value,
    ).toBe("");
  });

  it("offers each model with the class it is cleared for, so the choice is informed", async () => {
    mockApi();
    renderAt("/conversations/c1");
    expect(
      await screen.findByRole("option", {
        name: "anthropic/claude (up to Internal)",
      }),
    ).toBeTruthy();
    expect(
      screen.getByRole("option", {
        name: "openai/gpt-4o (up to Confidential)",
      }),
    ).toBeTruthy();
  });

  it("sends nothing for a blank message", async () => {
    mockApi();
    renderAt("/conversations/c1");
    await screen.findByLabelText("Message");
    expect(
      (screen.getByRole("button", { name: /Send/ }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    fireEvent.change(screen.getByLabelText("Message"), {
      target: { value: "   " },
    });
    expect(
      (screen.getByRole("button", { name: /Send/ }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
  });

  it("shows a refusal in words and keeps what the user typed", async () => {
    mockApi();
    post.mockRejectedValue(
      new Error(
        "Not authorized for confidential data: not_authorized:class_too_low",
      ),
    );
    renderAt("/conversations/c1");
    fireEvent.change(await screen.findByLabelText("Message"), {
      target: { value: "secret stuff" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Send/ }));
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Not authorized for confidential data",
    );
    expect(
      (screen.getByLabelText("Message") as HTMLTextAreaElement).value,
    ).toBe("secret stuff");
  });

  it("explains how to switch conversations on when the organization has not", async () => {
    mockApi();
    post.mockRejectedValue(
      new Error("Conversations are not enabled for this organization."),
    );
    renderAt("/conversations/c1");
    fireEvent.change(await screen.findByLabelText("Message"), {
      target: { value: "hi" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Send/ }));
    expect((await screen.findByRole("alert")).textContent).toContain(
      "An admin can turn them on under Policy",
    );
  });

  it("is read-only for a teammate: no composer, no delete", async () => {
    mockApi({
      conversation: {
        ...CONVERSATION,
        is_owner: false,
        owner_email: "alice@x.test",
        visibility: "team",
        team_id: "team1",
      },
    });
    renderAt("/conversations/c1");
    expect(
      await screen.findByText(/Read-only, owned by alice@x.test/),
    ).toBeTruthy();
    expect(screen.queryByLabelText("Message")).toBeNull();
    expect(screen.queryByRole("button", { name: /Delete/ })).toBeNull();
  });

  it("deletes after a confirmation", async () => {
    mockApi();
    del.mockResolvedValue(undefined as never);
    renderAt("/conversations/c1");
    fireEvent.click(await screen.findByRole("button", { name: /Delete/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    await waitFor(() =>
      expect(del).toHaveBeenCalledWith("/api/v1/conversations/c1", "tok"),
    );
  });

  it("says so when the conversation is not there for this user", async () => {
    get.mockImplementation(async (path: string) => {
      if (path.startsWith("/api/v1/conversations?")) return [];
      throw new Error("Conversation not found");
    });
    renderAt("/conversations/c1");
    expect(
      await screen.findByText(/does not exist or is not shared with you/),
    ).toBeTruthy();
  });
});

describe("the context drawer", () => {
  it("lists what was held back and why, with a preview of each held-back message", async () => {
    mockApi();
    renderAt("/conversations/c1");
    const answer = await screen.findByRole("article", {
      name: "Assistant, message 2",
    });
    fireEvent.click(
      within(answer).getByRole("button", { name: "Context sent" }),
    );
    const dialog = await screen.findByRole("dialog");
    expect(
      await within(dialog).findByText("Earlier messages held back"),
    ).toBeTruthy();
    expect(
      within(dialog).getAllByText(
        "More sensitive than this model is cleared for",
      ),
    ).toHaveLength(2);
    expect(within(dialog).getByText("Project Falcon price?")).toBeTruthy();
    expect(within(dialog).getByText("Routing enforced")).toBeTruthy();
  });

  it("says plainly when nothing was held back", async () => {
    mockApi();
    get.mockImplementation(async (path: string) => {
      if (path.endsWith("/context"))
        return { ...CONTEXT, withheld: [], included_turn_ids: ["t1", "t2"] };
      if (path === "/api/v1/conversations/c1") return CONVERSATION;
      if (path === "/api/v1/conversations/c1/turns") return TURNS;
      if (path === "/api/v1/conversations/models") return MODELS;
      return [];
    });
    renderAt("/conversations/c1");
    const answer = await screen.findByRole("article", {
      name: "Assistant, message 2",
    });
    fireEvent.click(
      within(answer).getByRole("button", { name: "Context sent" }),
    );
    expect(
      await screen.findByText(/Nothing\. The model saw the whole conversation/),
    ).toBeTruthy();
  });
});
