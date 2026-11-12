import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { PolicyPreviewResponse } from "../../api/types";
import { RoutingPreview } from "./RoutingPreview";

vi.mock("../../api/client", () => ({ apiClient: { post: vi.fn() } }));
const toastError = vi.hoisted(() => vi.fn());
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: toastError } }));

import { apiClient } from "../../api/client";
const post = vi.mocked(apiClient.post);

function result(over: Partial<PolicyPreviewResponse> = {}): PolicyPreviewResponse {
  return {
    verdict: "allowed",
    data_class: { class: "confidential", source: "detected", entities: ["ssn"] },
    policy: { mode: "enforce", allowed: true, action: "allow", reason_code: null, detail: null, triggered_rules: [] },
    routing: {
      current_mode: "enforce",
      requested: "openai/gpt-4o",
      model: "openai/gpt-4o",
      reason: "authorized",
      authorized: ["openai/gpt-4o"],
      excluded: {},
      key_alias: "prod-key",
    },
    fallback: null,
    not_evaluated: ["rate_limit", "budget", "upstream"],
    ...over,
  };
}

function renderPanel(unsaved = false) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RoutingPreview token="tok" unsaved={unsaved} />
    </QueryClientProvider>,
  );
}

function fill(model = "openai/gpt-4o", prompt = "my ssn is 123-45-6789") {
  fireEvent.change(screen.getByLabelText("Model"), { target: { value: model } });
  fireEvent.change(screen.getByLabelText("Prompt"), { target: { value: prompt } });
}

beforeEach(() => {
  post.mockReset();
  toastError.mockReset();
});
afterEach(cleanup);

describe("RoutingPreview", () => {
  it("does not call the API without a model and a prompt", () => {
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(post).not.toHaveBeenCalled();
    expect(toastError).toHaveBeenCalledWith("Enter a model and a prompt to preview.");
  });

  it("sends the request and shows the verdict, data class and routing", async () => {
    post.mockResolvedValue(result());
    renderPanel();
    fill();
    fireEvent.change(screen.getByLabelText(/Data class the caller asserts/), { target: { value: "secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));

    expect(await screen.findByText("Would be served")).toBeTruthy();
    expect(post).toHaveBeenCalledWith(
      "/api/v1/policy/preview",
      { model: "openai/gpt-4o", messages: [{ role: "user", content: "my ssn is 123-45-6789" }], data_class: "secret" },
      "tok",
    );
    expect(screen.getByText("Confidential (detected: ssn)")).toBeTruthy();
    expect(screen.getByText(/Served by openai\/gpt-4o/)).toBeTruthy();
    expect(screen.getByText(/through key prod-key/)).toBeTruthy();
    expect(screen.getByText(/Not checked here: rate limits, budgets, the provider call\./)).toBeTruthy();
  });

  it("shows what the caller would be told: the policy sentence first, else the routing one, nothing when allowed", async () => {
    const refusedRouting = {
      current_mode: "enforce" as const, requested: "openai/gpt-4o", model: null, reason: "not_authorized:class_too_low",
      authorized: [], excluded: {}, key_alias: null, explanation: "openai/gpt-4o is not approved for confidential data in your organization.",
    };
    post.mockResolvedValue(result({ verdict: "blocked_by_routing", routing: refusedRouting }));
    renderPanel();
    fill();
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(await screen.findByText("Caller would be told")).toBeTruthy();
    expect(screen.getByText("openai/gpt-4o is not approved for confidential data in your organization.")).toBeTruthy();
    cleanup();

    post.mockResolvedValue(
      result({
        verdict: "blocked_by_policy",
        policy: { mode: "enforce", allowed: false, action: "block", reason_code: "pii_detected", detail: "x", triggered_rules: [], explanation: "This request appears to contain personal or sensitive data that your organization's policy does not allow to be sent." },
        routing: refusedRouting,
      }),
    );
    renderPanel();
    fill();
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(await screen.findByText(/appears to contain personal or sensitive data/)).toBeTruthy();
    expect(screen.queryByText(/is not approved for confidential data/)).toBeNull();
    cleanup();

    post.mockResolvedValue(result());
    renderPanel();
    fill();
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    await screen.findByText("Would be served");
    expect(screen.queryByText("Caller would be told")).toBeNull();
  });

  it("explains a refusal: what was ruled out and why, and the fallback's fate", async () => {
    post.mockResolvedValue(
      result({
        verdict: "blocked_by_routing",
        routing: {
          current_mode: "enforce",
          requested: "openai/gpt-4o",
          model: null,
          reason: "not_authorized:class_too_low",
          authorized: ["local/llama"],
          excluded: { "openai/gpt-4o": "class_too_low" },
          key_alias: null,
        },
        fallback: { model: "openai/gpt-4o-mini", authorized: false, reason: "class_too_low" },
      }),
    );
    renderPanel();
    fill();
    fireEvent.change(screen.getByLabelText(/Fallback model/), { target: { value: "openai/gpt-4o-mini" } });
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));

    expect(await screen.findByText("Refused by routing")).toBeTruthy();
    expect(screen.getByText(/is not authorized: it is not cleared for this data class/)).toBeTruthy();
    expect(screen.getByText(/authorized for this request: local\/llama/)).toBeTruthy();
    expect(screen.getByText(/openai\/gpt-4o-mini: refused \(class_too_low\)/)).toBeTruthy();
    expect(post.mock.calls[0][1]).toMatchObject({ fallback_model: "openai/gpt-4o-mini" });
  });

  it("shows a policy block with its reason", async () => {
    post.mockResolvedValue(
      result({
        verdict: "blocked_by_policy",
        policy: { mode: "enforce", allowed: false, action: "block", reason_code: "pii_detected", detail: "SSN found", triggered_rules: [] },
      }),
    );
    renderPanel();
    fill();
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(await screen.findByText("Blocked by policy")).toBeTruthy();
    expect(screen.getByText("Blocked: pii_detected. SSN found")).toBeTruthy();
  });

  it("Enter in a text field runs the preview", async () => {
    post.mockResolvedValue(result());
    renderPanel();
    fill();
    fireEvent.keyDown(screen.getByLabelText("Model"), { key: "Enter" });
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
  });

  it("warns that unsaved edits are not part of the preview", () => {
    renderPanel(true);
    expect(screen.getByText(/your unsaved changes are not included until you save/)).toBeTruthy();
  });

  it("reports an API failure instead of showing a result", async () => {
    post.mockRejectedValue(new Error("gateway down"));
    renderPanel();
    fill();
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    await waitFor(() => expect(toastError).toHaveBeenCalledWith("gateway down"));
    expect(screen.queryByText("Would be served")).toBeNull();
  });
});
