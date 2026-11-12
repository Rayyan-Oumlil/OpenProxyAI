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
  apiClient: { get: vi.fn(), post: vi.fn(), del: vi.fn(), patch: vi.fn() },
}));

vi.mock("../../lib/streamTurn", () => {
  class StreamUnavailable extends Error {}
  return { streamTurn: vi.fn(), StreamUnavailable };
});

import { apiClient } from "../../api/client";
import { StreamUnavailable, streamTurn } from "../../lib/streamTurn";

const get = vi.mocked(apiClient.get);
const post = vi.mocked(apiClient.post);
const stream = vi.mocked(streamTurn);
const del = vi.mocked(apiClient.del);
const patch = vi.mocked(apiClient.patch);

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

const SPACES = [
  {
    id: "s1",
    name: "Q3 planning",
    team_id: null,
    owner_id: "u1",
    is_owner: true,
    conversation_count: 1,
    created_at: "2026-11-01T09:00:00Z",
  },
];

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
    if (path.startsWith("/api/v1/conversations?scope=mine&"))
      return overrides.list ?? [CONVERSATION];
    if (path === "/api/v1/spaces") return SPACES;
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
  stream.mockReset();
  del.mockReset();
  patch.mockReset();
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
    stream.mockResolvedValue(exchange(CONTEXT));
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
      expect(stream).toHaveBeenCalledWith(
        "c1",
        {
          content: "Summarise it",
          model: "anthropic/claude",
          data_class: "confidential",
        },
        "tok",
        expect.anything(),
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
    stream.mockRejectedValue(
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
    stream.mockRejectedValue(
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

  it("asks again for the whole answer when the organization cannot stream", async () => {
    mockApi();
    stream.mockRejectedValue(
      new StreamUnavailable("answers are checked first"),
    );
    post.mockResolvedValue(exchange(CONTEXT));
    renderAt("/conversations/c1");
    fireEvent.change(await screen.findByLabelText("Message"), {
      target: { value: "hi" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Send/ }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        "/api/v1/conversations/c1/turns",
        { content: "hi", model: "openai/gpt-4o" },
        "tok",
      ),
    );
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("shows the answer as it is written, then replaces it with the stored one", async () => {
    mockApi();
    let finish: (value: TurnExchange) => void = () => undefined;
    stream.mockImplementation(async (_id, _body, _token, handlers) => {
      handlers.onDelta("Hel");
      handlers.onDelta("lo");
      return new Promise<TurnExchange>((resolve) => {
        finish = resolve;
      });
    });
    renderAt("/conversations/c1");
    fireEvent.change(await screen.findByLabelText("Message"), {
      target: { value: "hi" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Send/ }));
    const writing = await screen.findByRole("article", {
      name: "Assistant, writing",
    });
    expect(writing.textContent).toContain("Hello");
    finish(exchange(CONTEXT));
    await waitFor(() =>
      expect(
        screen.queryByRole("article", { name: "Assistant, writing" }),
      ).toBeNull(),
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

describe("tags, search and spaces", () => {
  it("searches titles and tags through the server, not the browser", async () => {
    mockApi();
    renderAt("/conversations");
    await screen.findByRole("link", { name: /Q3 review/ });
    fireEvent.change(screen.getByLabelText("Search titles and tags"), {
      target: { value: "falcon" },
    });
    await waitFor(() =>
      expect(get).toHaveBeenCalledWith(
        "/api/v1/conversations?scope=mine&q=falcon",
        "tok",
      ),
    );
  });

  it("filters by a tag chip and clears it again", async () => {
    mockApi();
    renderAt("/conversations");
    const chip = await screen.findByRole("button", { name: "finance" });
    expect(chip.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(chip);
    await waitFor(() =>
      expect(get).toHaveBeenCalledWith(
        "/api/v1/conversations?scope=mine&tag=finance",
        "tok",
      ),
    );
    expect(chip.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(chip);
    expect(chip.getAttribute("aria-pressed")).toBe("false");
  });

  it("filters by space", async () => {
    mockApi();
    renderAt("/conversations");
    await screen.findByRole("option", { name: "Q3 planning" });
    fireEvent.change(screen.getByLabelText("Space"), {
      target: { value: "s1" },
    });
    await waitFor(() =>
      expect(get).toHaveBeenCalledWith(
        "/api/v1/conversations?scope=mine&space_id=s1",
        "tok",
      ),
    );
  });

  it("says so when nothing matches", async () => {
    mockApi({ list: [] });
    renderAt("/conversations");
    fireEvent.change(await screen.findByLabelText("Search titles and tags"), {
      target: { value: "zzz" },
    });
    expect(await screen.findByText("No conversation matches.")).toBeTruthy();
  });

  it("keeps a new conversation private and unshareable when 'Keep private' is ticked", async () => {
    mockApi();
    post.mockResolvedValue({ ...CONVERSATION, id: "c9" });
    renderAt("/conversations");
    fireEvent.click(
      await screen.findByRole("button", { name: /New conversation/ }),
    );
    fireEvent.change(await screen.findByLabelText("Title"), {
      target: { value: "Secret" },
    });
    await screen.findByRole("option", { name: "Team: Finance" });
    fireEvent.change(screen.getByLabelText("Share with"), {
      target: { value: "team1" },
    });
    fireEvent.click(screen.getByLabelText(/Keep private/));
    expect(
      (screen.getByLabelText("Share with") as HTMLSelectElement).disabled,
    ).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Start conversation" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        "/api/v1/conversations",
        { title: "Secret", tags: ["private"] },
        "tok",
      ),
    );
  });

  it("files a new conversation in the chosen space", async () => {
    mockApi();
    post.mockResolvedValue({ ...CONVERSATION, id: "c9" });
    renderAt("/conversations");
    fireEvent.click(
      await screen.findByRole("button", { name: /New conversation/ }),
    );
    fireEvent.change(await screen.findByLabelText("Title"), {
      target: { value: "Plan" },
    });
    const dialog = screen.getByRole("dialog", { name: "New conversation" });
    await within(dialog).findByRole("option", { name: "Q3 planning" });
    fireEvent.change(within(dialog).getByLabelText("Space"), {
      target: { value: "s1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Start conversation" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        "/api/v1/conversations",
        { title: "Plan", tags: [], space_id: "s1" },
        "tok",
      ),
    );
  });

  it("edits the tags and space of your own conversation, and says that making it private stops sharing", async () => {
    mockApi({
      conversation: { ...CONVERSATION, visibility: "team", team_id: "team1" },
    });
    patch.mockResolvedValue(CONVERSATION);
    renderAt("/conversations/c1");
    fireEvent.click(await screen.findByRole("button", { name: /Details/ }));
    const dialog = await screen.findByRole("dialog", {
      name: "Conversation details",
    });
    fireEvent.change(within(dialog).getByLabelText(/Tags/), {
      target: { value: "ops,  q3" },
    });
    fireEvent.click(within(dialog).getByLabelText(/Keep private/));
    expect(within(dialog).getByText(/Saving stops sharing it/)).toBeTruthy();
    await within(dialog).findByRole("option", { name: "Q3 planning" });
    fireEvent.change(within(dialog).getByLabelText("Space"), {
      target: { value: "s1" },
    });
    fireEvent.click(
      within(dialog).getByRole("button", { name: "Save details" }),
    );
    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith(
        "/api/v1/conversations/c1",
        { tags: ["ops", "q3", "private"], space_id: "s1" },
        "tok",
      ),
    );
  });

  it("takes a conversation out of its space when 'No space' is chosen", async () => {
    mockApi({
      conversation: {
        ...CONVERSATION,
        space_id: "s1",
        space_name: "Q3 planning",
      },
    });
    patch.mockResolvedValue(CONVERSATION);
    renderAt("/conversations/c1");
    fireEvent.click(await screen.findByRole("button", { name: /Details/ }));
    const dialog = await screen.findByRole("dialog", {
      name: "Conversation details",
    });
    await within(dialog).findByRole("option", { name: "Q3 planning" });
    fireEvent.change(within(dialog).getByLabelText("Space"), {
      target: { value: "" },
    });
    fireEvent.click(
      within(dialog).getByRole("button", { name: "Save details" }),
    );
    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith(
        "/api/v1/conversations/c1",
        { tags: ["finance"], space_id: null },
        "tok",
      ),
    );
  });

  it("offers no Details button on a conversation a teammate shared with you", async () => {
    mockApi({
      conversation: {
        ...CONVERSATION,
        is_owner: false,
        owner_email: "alice@x.test",
      },
    });
    renderAt("/conversations/c1");
    await screen.findByText(/Read-only, owned by alice@x.test/);
    expect(screen.queryByRole("button", { name: /Details/ })).toBeNull();
  });

  it("creates, renames and deletes spaces from the Spaces dialog", async () => {
    mockApi();
    post.mockResolvedValue(SPACES[0]);
    patch.mockResolvedValue(SPACES[0]);
    del.mockResolvedValue(undefined);
    renderAt("/conversations");
    fireEvent.click(await screen.findByRole("button", { name: /^Spaces$/ }));
    const dialog = await screen.findByRole("dialog", { name: "Spaces" });

    fireEvent.change(within(dialog).getByLabelText("New space"), {
      target: { value: "Roadmap" },
    });
    await within(dialog).findByRole("option", { name: "Team: Finance" });
    fireEvent.change(within(dialog).getByLabelText("Visible to"), {
      target: { value: "team1" },
    });
    fireEvent.click(
      within(dialog).getByRole("button", { name: "Create space" }),
    );
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        "/api/v1/spaces",
        { name: "Roadmap", team_id: "team1" },
        "tok",
      ),
    );

    const name = await within(dialog).findByLabelText(
      "Name of space Q3 planning",
    );
    fireEvent.change(name, { target: { value: "Q4 planning" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Rename" }));
    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith(
        "/api/v1/spaces/s1",
        { name: "Q4 planning" },
        "tok",
      ),
    );

    fireEvent.click(
      within(dialog).getByRole("button", { name: "Delete space Q3 planning" }),
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Delete space" }),
    );
    await waitFor(() =>
      expect(del).toHaveBeenCalledWith("/api/v1/spaces/s1", "tok"),
    );
  });
});
