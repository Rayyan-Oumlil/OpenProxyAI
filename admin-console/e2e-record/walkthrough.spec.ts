import { expect, test, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";

/**
 * The 3-minute walkthrough (docs/getting-started/walkthrough.md) as a recording: it drives the real console and
 * the real gateway of a running demo stack, with a caption on screen for each step. Every outcome is asserted,
 * so the recording cannot show something the product does not do.
 */
const API = process.env.API_URL ?? "http://localhost:8000";
const KEY = "opai_dev_demo0001_00000000000000000000000000demo01fea5";
const INTERN = "opai_dev_demo0002_00000000000000000000000000demo02741f";
const OUT = "walkthrough-video/openproxyai-walkthrough.webm";

async function caption(page: Page, text: string): Promise<void> {
  await page.evaluate((t) => {
    let el = document.getElementById("rec-caption");
    if (!el) {
      el = document.createElement("div");
      el.id = "rec-caption";
      el.setAttribute("aria-hidden", "true");
      Object.assign(el.style, {
        position: "fixed", left: "50%", bottom: "28px", transform: "translateX(-50%)", zIndex: "99999",
        maxWidth: "980px", padding: "14px 26px", borderRadius: "12px", background: "rgba(8,10,14,0.92)", color: "#fff",
        font: "600 22px/1.3 Inter, system-ui, sans-serif", textAlign: "center", boxShadow: "0 8px 30px rgba(0,0,0,0.45)",
      });
      document.body.appendChild(el);
    }
    el.textContent = t;
  }, text);
}

async function chat(page: Page, key: string, content: string): Promise<{ status: number; body: string }> {
  const response = await page.request.post(`${API}/v1/chat/completions`, {
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    data: { model: "openai/gpt-4o-mini", messages: [{ role: "user", content }] },
  });
  return { status: response.status(), body: await response.text() };
}

const beat = (page: Page, ms = 2600) => page.waitForTimeout(ms);

test("OpenProxyAI in three minutes", async ({ page }) => {
  mkdirSync("walkthrough-video", { recursive: true });

  // Sign in as the demo admin.
  await page.goto("/");
  await page.getByLabel("Email").fill("admin@example.com");
  await page.getByLabel("Password").fill("DemoPass123!");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.locator("main").first().waitFor();
  await caption(page, "OpenProxyAI: one gateway between your teams and every LLM provider");
  await beat(page, 3200);

  // 0:00 One key, any model
  await caption(page, "Teams use one key. Every request is checked, priced and recorded.");
  const allowed = await chat(page, KEY, "Summarise our Q3 roadmap in one line.");
  expect(allowed.status).toBe(200);
  await caption(page, "An allowed request goes through: HTTP 200");
  await beat(page);

  // 0:40 Policy blocks before the provider
  const pii = await chat(page, KEY, "Customer SSN is 123-45-6789, draft the email.");
  expect(pii.status).toBe(403);
  await caption(page, "PII in the prompt: blocked by policy, HTTP 403. The provider never sees it.");
  await beat(page, 3400);
  const keyword = await chat(page, KEY, "What is the status of project-phoenix?");
  expect(keyword.status).toBe(403);
  await caption(page, "A blocked keyword: HTTP 403 as well");
  await beat(page);

  // The audit record
  await page.getByRole("link", { name: "Request logs" }).click();
  const table = page.getByRole("table", { name: "Request logs" });
  await expect(table.getByText("Blocked").first()).toBeVisible();
  await caption(page, "Every request is in the audit log, with its policy decision");
  await beat(page, 3200);
  await table.getByText("Blocked").first().click();
  await page.getByRole("link", { name: "Open full trace" }).click();
  await expect(page.getByRole("heading", { name: "Request trace" })).toBeVisible();
  await caption(page, "The trace: policy stopped it. No upstream call, no cost.");
  await beat(page, 4200);

  // 1:20 A budget that stops spend
  await caption(page, "The intern's key is capped at one cent a day");
  const costly = await chat(page, INTERN, "Summarise the board deck [big-usage]");
  expect(costly.status).toBe(200);
  await caption(page, "One large request: HTTP 200 ...");
  await beat(page, 2200);
  let stopped = await chat(page, INTERN, "And one more question.");
  for (let i = 0; i < 8 && stopped.status === 200; i += 1) {
    await page.waitForTimeout(1000);
    stopped = await chat(page, INTERN, "And one more question.");
  }
  expect(stopped.status).toBe(429);
  expect(stopped.body).toContain("user_budget_daily_usd");
  await caption(page, "... and the next is refused before it reaches the provider (daily budget reached)");
  await beat(page, 3800);

  // 2:00 Agents and tools
  await page.getByRole("link", { name: "MCP servers" }).click();
  await expect(page.getByRole("heading", { name: "MCP servers" })).toBeVisible();
  await caption(page, "Agents call tools through the same gateway");
  await beat(page);
  await page.getByRole("cell", { name: /github/ }).first().click();
  const drift = page.getByRole("group", { name: "Changes to deploy since approval" });
  await expect(drift).toBeVisible();
  await caption(page, "A tool changed after approval: its new description hides an instruction. Agents still see the approved text.");
  await beat(page, 5200);
  const denied = await page.request.post(`${API}/v1/mcp`, {
    headers: { Authorization: `Bearer ${KEY}`, "Content-Type": "application/json" },
    data: { jsonrpc: "2.0", id: 1, method: "tools/call", params: { name: "github__deploy", arguments: {} } },
  });
  expect((await denied.text())).toContain("-32004");
  await caption(page, "Calling the drifted tool is refused (-32004). The server was never contacted.");
  await beat(page, 4200);

  // Policy and navigation
  await page.getByRole("link", { name: "Policy" }).first().click();
  await expect(page.getByRole("tablist", { name: "Policy sections" })).toBeVisible();
  await caption(page, "Policy is configured in the console: enforcement, data protection, rate limits");
  await beat(page);
  await page.getByRole("tab", { name: "Data protection" }).click();
  await beat(page, 2400);

  await page.keyboard.press("Control+k");
  await caption(page, "Ctrl+K jumps anywhere");
  await page.getByRole("combobox", { name: "Go to page or action" }).fill("dashboard");
  await beat(page, 1600);
  await page.keyboard.press("Enter");

  // 2:40 Close
  await expect(page.getByRole("heading", { name: "Gateway dashboard" })).toBeVisible();
  await caption(page, "Spend, latency, policy blocks and the month's budget burn-down in one place");
  await beat(page, 5200);
  await caption(page, "OpenProxyAI: governance you can demo");
  await beat(page, 3000);

  const video = page.video();
  await page.close();
  await video?.saveAs(OUT);
});
