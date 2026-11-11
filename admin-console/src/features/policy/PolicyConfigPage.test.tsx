import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { OrganizationResponse } from "../../api/types";
import { PolicyConfigPage } from "./PolicyConfigPage";

const auth = vi.hoisted(() => ({ role: "admin" }));
vi.mock("../../state/AuthContext", () => ({ useAuth: () => ({ token: "tok", user: { role: auth.role } }) }));
vi.mock("../../api/client", () => ({ apiClient: { get: vi.fn(), patch: vi.fn(), post: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { apiClient } from "../../api/client";

const get = vi.mocked(apiClient.get);
const patch = vi.mocked(apiClient.patch);
const post = vi.mocked(apiClient.post);

function org(policy: Record<string, unknown> = {}): OrganizationResponse {
  return {
    id: "o1",
    name: "Demo Org",
    slug: "demo",
    plan: "starter",
    settings: {
      policy: {
        enforcement_mode: "enforce",
        allowed_models: ["gpt-4o"],
        blocked_keywords: ["project-phoenix"],
        pii_detection_enabled: true,
        pii_entities: ["EMAIL_ADDRESS"],
        model_rate_limits: {},
        ...policy,
      },
    },
    budget_monthly_usd: null,
    is_active: true,
    created_at: "2026-11-01T10:00:00Z",
  } as OrganizationResponse;
}

function mockApi(templates: unknown[] = []) {
  get.mockImplementation(async (path: string) => {
    if (path === "/api/v1/organizations/current") return org();
    if (path === "/api/v1/organizations/current/policy/templates") return templates;
    throw new Error(`unmocked ${path}`);
  });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <PolicyConfigPage />
    </QueryClientProvider>,
  );
}

const tab = (name: string) => screen.getByRole("tab", { name });
const mode = (name: string) => screen.getByRole("radio", { name: new RegExp(`^${name}`) }) as HTMLInputElement;

beforeEach(() => {
  get.mockReset();
  patch.mockReset();
  post.mockReset();
  patch.mockResolvedValue({});
  auth.role = "admin";
});
afterEach(cleanup);

describe("PolicyConfigPage", () => {
  it("groups the settings into labelled tabs, starting on Enforcement", async () => {
    mockApi();
    renderPage();
    await screen.findByRole("tablist", { name: "Policy sections" });
    expect(["Enforcement", "Data protection", "Data and routing", "Evaluation", "Rate limits", "Templates"].map((n) => tab(n).getAttribute("aria-selected"))).toEqual(["true", "false", "false", "false", "false", "false"]);
    expect(screen.getByRole("heading", { name: "Model Allowlist" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "PII Detection" })).toBeNull();
  });

  it("switches tabs with the mouse and with the arrow keys", async () => {
    mockApi();
    renderPage();
    await screen.findByRole("tablist");
    fireEvent.mouseDown(tab("Data protection"), { button: 0 });
    expect(await screen.findByRole("heading", { name: "PII Detection" })).toBeTruthy();

    tab("Data protection").focus();
    fireEvent.keyDown(tab("Data protection"), { key: "ArrowRight" });
    expect(await screen.findByRole("heading", { name: "Routing" })).toBeTruthy();
  });

  it("edits data classes and routing on their tab and saves them with the rest of the policy", async () => {
    mockApi();
    renderPage();
    await screen.findByRole("tablist");
    fireEvent.mouseDown(tab("Data and routing"), { button: 0 });
    await screen.findByRole("heading", { name: "Data classes" });

    fireEvent.click(screen.getByRole("radio", { name: /^Preview \(log only\)/ }));
    fireEvent.change(screen.getByLabelText("Detected kind"), { target: { value: "US_SSN" } });
    fireEvent.change(screen.getByLabelText("Class"), { target: { value: "secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Add class for detected kind" }));
    expect(await screen.findByText("US_SSN")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Save policy" }));
    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    expect(patch.mock.calls[0][1]).toEqual({ routing_mode: "log_only", data_class_map: { US_SSN: "secret" } });
  });

  it("allows provider-side state only when the box is ticked, and saves only that field", async () => {
    mockApi();
    renderPage();
    await screen.findByRole("tablist");
    fireEvent.mouseDown(tab("Data and routing"), { button: 0 });
    const box = (await screen.findByLabelText("Allow requests to keep state at the provider")) as HTMLInputElement;
    expect(box.checked).toBe(false);
    fireEvent.click(box);
    fireEvent.click(screen.getByRole("button", { name: "Save policy" }));
    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    expect(patch.mock.calls[0][1]).toEqual({ allow_provider_response_state: true });
  });

  it("turns capture on at 10%, lets the share be set, and saves only the rate", async () => {
    mockApi();
    renderPage();
    await screen.findByRole("tablist");
    fireEvent.mouseDown(tab("Evaluation"), { button: 0 });
    await screen.findByRole("heading", { name: "Capture traffic for evaluation" });
    expect(screen.queryByLabelText("Share of requests kept (%)")).toBeNull();
    fireEvent.click(screen.getByLabelText("Keep a sample of delivered requests"));
    const share = screen.getByLabelText("Share of requests kept (%)") as HTMLInputElement;
    expect(share.value).toBe("10");
    fireEvent.change(share, { target: { value: "25" } });
    fireEvent.click(screen.getByRole("button", { name: "Save policy" }));
    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    expect(patch.mock.calls[0][1]).toEqual({ payload_capture_sample_rate: 0.25 });
  });

  it("keeps the capture share between 1 and 100", async () => {
    mockApi();
    renderPage();
    await screen.findByRole("tablist");
    fireEvent.mouseDown(tab("Evaluation"), { button: 0 });
    fireEvent.click(await screen.findByLabelText("Keep a sample of delivered requests"));
    const share = screen.getByLabelText("Share of requests kept (%)") as HTMLInputElement;
    fireEvent.change(share, { target: { value: "500" } });
    expect(share.value).toBe("100");
    fireEvent.change(share, { target: { value: "0" } });
    expect(share.value).toBe("1");
  });

  it("turning capture off again sends zero", async () => {
    get.mockImplementation(async (path: string) => (path === "/api/v1/organizations/current" ? org({ payload_capture_sample_rate: 0.5 }) : []));
    renderPage();
    await screen.findByRole("tablist");
    fireEvent.mouseDown(tab("Evaluation"), { button: 0 });
    const toggle = (await screen.findByLabelText("Keep a sample of delivered requests")) as HTMLInputElement;
    expect(toggle.checked).toBe(true);
    fireEvent.click(toggle);
    fireEvent.click(screen.getByRole("button", { name: "Save policy" }));
    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    expect(patch.mock.calls[0][1]).toEqual({ payload_capture_sample_rate: 0 });
  });

  it("enables the promotion gate with its thresholds", async () => {
    mockApi();
    renderPage();
    await screen.findByRole("tablist");
    fireEvent.mouseDown(tab("Evaluation"), { button: 0 });
    fireEvent.click(await screen.findByLabelText("Require a passing eval run before a prompt goes live"));
    expect((screen.getByLabelText("Pass rate required (%)") as HTMLInputElement).value).toBe("80");
    fireEvent.change(screen.getByLabelText("Pass rate required (%)"), { target: { value: "90" } });
    fireEvent.change(screen.getByLabelText("Items the run must score"), { target: { value: "25" } });
    fireEvent.click(screen.getByRole("button", { name: "Save policy" }));
    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    expect(patch.mock.calls[0][1]).toEqual({ prompt_promotion_gate: true, prompt_gate_min_pass_rate: 0.9, prompt_gate_min_items: 25 });
  });

  it("does not offer the evaluation controls to a non-admin", async () => {
    auth.role = "viewer";
    mockApi();
    renderPage();
    await screen.findByRole("tablist");
    fireEvent.mouseDown(tab("Evaluation"), { button: 0 });
    expect((await screen.findByLabelText("Keep a sample of delivered requests") as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByLabelText("Require a passing eval run before a prompt goes live") as HTMLInputElement).disabled).toBe(true);
  });

  it("Enter in the detected-kind field adds a row and does not save the policy", async () => {
    mockApi();
    renderPage();
    await screen.findByRole("tablist");
    fireEvent.mouseDown(tab("Data and routing"), { button: 0 });
    const field = await screen.findByLabelText("Detected kind");
    fireEvent.change(field, { target: { value: "email" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(await screen.findByText("email")).toBeTruthy();
    expect(patch).not.toHaveBeenCalled();
  });

  it("rejects a malformed detected-kind name", async () => {
    mockApi();
    renderPage();
    await screen.findByRole("tablist");
    fireEvent.mouseDown(tab("Data and routing"), { button: 0 });
    fireEvent.change(await screen.findByLabelText("Detected kind"), { target: { value: "bad name!" } });
    fireEvent.click(screen.getByRole("button", { name: "Add class for detected kind" }));
    expect(screen.queryByRole("list", { name: "Classes for detected data" })).toBeNull();
    expect(screen.getByText("All changes saved.")).toBeTruthy();
  });

  it("hides the preview panel and the editing controls from a non-admin", async () => {
    auth.role = "viewer";
    mockApi();
    renderPage();
    await screen.findByRole("tablist");
    fireEvent.mouseDown(tab("Data and routing"), { button: 0 });
    await screen.findByRole("heading", { name: "Routing" });
    expect(screen.queryByRole("heading", { name: "Preview a request" })).toBeNull();
    expect(screen.queryByLabelText("Detected kind")).toBeNull();
    expect((screen.getByRole("radio", { name: /^Enforce/ }) as HTMLInputElement).disabled).toBe(true);
  });

  it("keeps an edit made on one tab while visiting others, and saves them all in one request, sending only what changed", async () => {
    mockApi();
    renderPage();
    await screen.findByRole("tablist");

    fireEvent.click(mode("Log Only"));
    fireEvent.mouseDown(tab("Data protection"), { button: 0 });
    const guardrail = await screen.findByLabelText(/Prompt Injection Detection/);
    fireEvent.click(guardrail);
    fireEvent.mouseDown(tab("Enforcement"), { button: 0 });
    await screen.findByRole("heading", { name: "Model Allowlist" });
    expect(mode("Log Only").checked).toBe(true); // survived the round trip

    fireEvent.click(screen.getByRole("button", { name: "Save policy" }));
    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    const [path, body] = patch.mock.calls[0];
    expect(path).toBe("/api/v1/organizations/current/policy");
    expect(body).toEqual({ enforcement_mode: "log_only", prompt_injection_detection_enabled: true });
  });

  it("adds a blocked keyword on Enter and removes one with its named button", async () => {
    mockApi();
    renderPage();
    const keywords = await screen.findByRole("textbox", { name: "Blocked keywords" });
    fireEvent.change(keywords, { target: { value: "secret-roadmap" } });
    fireEvent.keyDown(keywords, { key: "Enter" });
    expect(await screen.findByText("secret-roadmap")).toBeTruthy();
    expect(await screen.findByText("You have unsaved changes.")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Remove project-phoenix" }));
    await waitFor(() => expect(screen.queryByText("project-phoenix")).toBeNull());

    fireEvent.click(screen.getByRole("button", { name: "Save policy" }));
    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    expect(patch.mock.calls[0][1]).toEqual({ blocked_keywords: ["secret-roadmap"] });
  });

  it("does not resend a switch the admin did not touch: PII detection, already on, is left out of the save", async () => {
    // A free-plan organization has PII detection on by default; the server refuses an explicit "true" on that plan,
    // so resending it would make every save fail with a 402.
    mockApi();
    renderPage();
    await screen.findByRole("tablist");
    fireEvent.click(mode("Observe"));
    fireEvent.click(screen.getByRole("button", { name: "Save policy" }));
    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    expect(patch.mock.calls[0][1]).toEqual({ enforcement_mode: "observe" });
    expect(patch.mock.calls[0][1]).not.toHaveProperty("pii_detection_enabled");
  });

  it("ignores a duplicate tag", async () => {
    mockApi();
    renderPage();
    const keywords = await screen.findByRole("textbox", { name: "Blocked keywords" });
    fireEvent.change(keywords, { target: { value: "project-phoenix" } });
    fireEvent.keyDown(keywords, { key: "Enter" });
    expect(screen.getAllByText("project-phoenix")).toHaveLength(1);
    expect(screen.getByText("All changes saved.")).toBeTruthy();
  });

  it("shows unsaved changes, and Discard restores what the server has", async () => {
    mockApi();
    renderPage();
    await screen.findByText("All changes saved.");
    expect((screen.getByRole("button", { name: "Save policy" }) as HTMLButtonElement).disabled).toBe(true);

    fireEvent.click(mode("Observe"));
    expect(await screen.findByText("You have unsaved changes.")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Save policy" }) as HTMLButtonElement).disabled).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Discard" }));
    expect(await screen.findByText("All changes saved.")).toBeTruthy();
    expect(mode("Enforce").checked).toBe(true);
  });

  it("is read-only for a non-admin: no save bar, a notice, and disabled controls", async () => {
    auth.role = "viewer";
    mockApi();
    renderPage();
    await screen.findByRole("tablist");
    expect(screen.getByText(/You need admin privileges/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Save policy" })).toBeNull();
    expect(mode("Observe").disabled).toBe(true);
    expect((screen.getByRole("textbox", { name: "Blocked keywords" }) as HTMLInputElement).disabled).toBe(true);
    expect(screen.queryByRole("button", { name: "Remove project-phoenix" })).toBeNull();
  });

  it("lists compliance templates and applies one only after the confirmation dialog", async () => {
    mockApi([{ name: "healthcare_hipaa", description: "Guardrails for healthcare", configures: ["PII detection on"] }]);
    post.mockResolvedValue({});
    renderPage();
    await screen.findByRole("tablist");
    fireEvent.mouseDown(tab("Templates"), { button: 0 });
    expect(await screen.findByRole("heading", { name: "Quick Setup" })).toBeTruthy();
    expect(screen.getByText("Healthcare (HIPAA)")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Apply Template" }));
    expect(await screen.findByRole("dialog", { name: "Apply compliance template" })).toBeTruthy();
    expect(post).not.toHaveBeenCalled(); // choosing a template alone changes nothing

    fireEvent.click(screen.getAllByRole("button", { name: "Apply Template" }).at(-1)!);
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/api/v1/organizations/current/policy/apply-template", { template: "healthcare_hipaa" }, "tok"),
    );
  });

  it("says when there are no templates, instead of an empty tab", async () => {
    mockApi([]);
    renderPage();
    await screen.findByRole("tablist");
    fireEvent.mouseDown(tab("Templates"), { button: 0 });
    expect(await screen.findByText(/No compliance templates are available/)).toBeTruthy();
  });

  it("shows an error when the policy cannot be loaded", async () => {
    get.mockRejectedValue(new Error("boom"));
    renderPage();
    expect(await screen.findByText("Unable to load policy")).toBeTruthy();
  });
});
