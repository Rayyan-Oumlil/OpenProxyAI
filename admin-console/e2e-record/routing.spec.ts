import { expect, test, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";

/**
 * The classification-aware routing demo as a recording (docs/getting-started/walkthrough.md, "route by data class"):
 * preview a request, see it refused for Confidential data on a model cleared only for Internal, enforce the rule,
 * then watch a real request get refused with HTTP 446 and read the reason in the audit trace.
 *
 * It drives a RUNNING demo stack, like walkthrough.spec.ts, and asserts every outcome, so the video cannot show
 * something the product does not do. The captions sit at the TOP of the page: at the bottom they hide the verdict.
 *
 *   docker compose -f docker-compose.demo.yml up -d --build --wait api console
 *   npm run record:routing
 *
 * It registers two models on first run (and leaves routing off when it ends), so it can be repeated.
 */
const API = process.env.API_URL ?? "http://localhost:8000";
const KEY = "opai_dev_demo0001_00000000000000000000000000demo01fea5";
const OUT = "walkthrough-video/openproxyai-routing.webm";
const SENSITIVE_PROMPT = "Summarise our Q3 customer contracts in one line.";

type Json = Record<string, unknown> | unknown[] | null;

async function api(method: string, path: string, token: string, body?: object, headers: Record<string, string> = {}): Promise<{ status: number; body: Json }> {
  const response = await fetch(API + path, {
    method,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...headers },
    body: body ? JSON.stringify(body) : undefined,
  });
  return { status: response.status, body: (await response.json().catch(() => null)) as Json };
}

/** Two models behind one internal endpoint: the cheap one cleared for Internal data, the other for Confidential. */
async function registerModels(token: string): Promise<void> {
  const existing = await api("GET", "/api/v1/model-registry", token);
  if (Array.isArray(existing.body) && existing.body.length >= 2) return;
  const key = await api("POST", "/api/v1/provider-keys", token, {
    provider: "openai", api_key: "sk-demo-internal", key_alias: "internal-llm", api_base: "http://fake-llm:9090/v1",
    is_internal: true, max_data_class: "confidential", weight: 1,
  });
  expect(key.status).toBe(201);
  const keyId = (key.body as { id: string }).id;
  for (const [model, dataClass, cost] of [["openai/gpt-4o-mini", "internal", "low"], ["openai/gpt-4o", "confidential", "high"]]) {
    const entry = await api("POST", "/api/v1/model-registry", token, {
      model_id: model, provider_key_id: keyId, max_data_class: dataClass, regions: ["us"], capabilities: ["VISION"], cost_tier: cost,
    });
    expect(entry.status).toBe(201);
  }
}

async function installCaption(page: Page): Promise<void> {
  await page.addInitScript(() => {
    (window as unknown as { __caption: (t: string) => void }).__caption = (text: string) => {
      let el = document.getElementById("rec-caption");
      if (!el) {
        el = document.createElement("div");
        el.id = "rec-caption";
        el.setAttribute("aria-hidden", "true");
        Object.assign(el.style, {
          position: "fixed", left: "50%", top: "14px", transform: "translateX(-50%)", zIndex: "99999", maxWidth: "960px",
          padding: "14px 22px", borderRadius: "12px", background: "rgba(10,15,30,0.92)", color: "#fff",
          font: "600 22px/1.35 Inter, system-ui, sans-serif", textAlign: "center", pointerEvents: "none",
        });
        document.body.appendChild(el);
      }
      el.textContent = text;
    };
  });
}

const caption = (page: Page, text: string) => page.evaluate((t) => (window as unknown as { __caption: (s: string) => void }).__caption(t), text);
const beat = (page: Page, ms = 3000) => page.waitForTimeout(ms);
const centered = (page: Page, text: string) => page.getByText(text).evaluate((el) => el.scrollIntoView({ block: "center" }));

test("Route by data class: preview, enforce, refuse", async ({ page }) => {
  mkdirSync("walkthrough-video", { recursive: true });
  await installCaption(page);
  await page.addInitScript(() => localStorage.setItem("openproxy_onboarding_dismissed", "1"));

  const login = await fetch(`${API}/api/v1/auth/login`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "admin@example.com", password: "DemoPass123!" }),
  });
  const token = ((await login.json()) as { access_token: string }).access_token;
  await registerModels(token);

  await page.goto("/");
  await page.getByLabel("Email").fill("admin@example.com");
  await page.getByLabel("Password").fill("DemoPass123!");
  await caption(page, "OpenProxyAI: decide which AI model may see which data");
  await beat(page, 3200);
  await page.getByRole("button", { name: "Sign in" }).click();
  // The sign-in page has a <main> too, so wait for a link that only the signed-in shell has.
  await expect(page.getByRole("link", { name: "Request logs" })).toBeVisible();

  // The registry: each model and the most sensitive data it may receive.
  await page.goto("/model-registry");
  await page.locator("main").first().waitFor();
  await caption(page, "Each model is registered with the most sensitive data it may receive");
  await beat(page, 4500);

  // Routing on, in preview first.
  await page.goto("/policy");
  await page.getByRole("tab", { name: "Data and routing" }).click();
  await caption(page, "Turn routing on in two steps: preview first, then enforce");
  await page.getByRole("radio", { name: /^Preview \(log only\)/ }).click();
  await page.getByRole("button", { name: "Save policy" }).click();
  await expect(page.getByText("All changes saved.")).toBeVisible();
  await beat(page, 1500);

  // Preview: refused for Confidential on the Internal-only model, then served by the model cleared for it.
  await caption(page, "Preview a request before it is sent: nothing is called, logged or counted");
  const model = page.getByLabel("Model", { exact: true });
  await model.fill("openai/gpt-4o-mini");
  await page.getByLabel("Prompt").fill(SENSITIVE_PROMPT);
  await page.getByLabel(/Data class the caller asserts/).selectOption("confidential");
  await page.getByRole("button", { name: "Preview", exact: true }).click();
  await expect(page.getByText("Would be refused if routing were enforced")).toBeVisible();
  await caption(page, "Confidential data, and this model is only cleared for Internal: it would be refused");
  await centered(page, "Would be refused if routing were enforced");
  await beat(page, 6500);

  await model.fill("openai/gpt-4o");
  await page.getByRole("button", { name: "Preview", exact: true }).click();
  await expect(page.getByText("Would be served")).toBeVisible();
  await caption(page, "The model cleared for Confidential would serve it");
  await centered(page, "Would be served");
  await beat(page, 5500);

  // Policy checks run before routing.
  await page.getByLabel("Prompt").fill("Customer SSN is 123-45-6789, draft the email.");
  await page.getByLabel(/Data class the caller asserts/).selectOption("");
  await page.getByRole("button", { name: "Preview", exact: true }).click();
  await expect(page.getByText("Blocked by policy")).toBeVisible();
  await caption(page, "Policy checks run first: a prompt with an SSN is blocked outright");
  await centered(page, "Blocked by policy");
  await beat(page, 5500);

  // Enforce, then a real request.
  await caption(page, "Now enforce it");
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.getByRole("radio", { name: /^Enforce/ }).click();
  await page.getByRole("button", { name: "Save policy" }).click();
  await expect(page.getByText("All changes saved.")).toBeVisible();
  const refused = await api("POST", "/v1/chat/completions", KEY, {
    model: "openai/gpt-4o-mini", messages: [{ role: "user", content: SENSITIVE_PROMPT }],
  }, { "x-openproxy-data-class": "confidential" });
  expect(refused.status).toBe(446);
  await caption(page, "A real request for Confidential data to that model: refused before any provider call");
  await beat(page, 3500);

  // The audit trail says why.
  await page.goto("/logs");
  await page.locator("main").first().waitFor();
  await page.getByText("openai/gpt-4o-mini").first().click();
  await page.getByRole("link", { name: /Open full trace/ }).click();
  await expect(page.getByRole("heading", { name: "Request trace" })).toBeVisible();
  await caption(page, "Every refusal is in the audit trail, with the reason in plain words");
  await beat(page, 7000);

  await caption(page, "Open source, Apache-2.0: github.com/Rayyan-Oumlil/OpenProxyAI");
  await beat(page, 5000);

  // Leave the demo org as it was found.
  await api("PATCH", "/api/v1/organizations/current/policy", token, { routing_mode: "off" });
  const video = page.video();
  await page.close();
  await video?.saveAs(OUT);
});
