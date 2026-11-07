const { chromium } = require("playwright");
const fs = require("fs"),
  path = require("path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, ".."),
  out = path.join(root, "test-results", "research-ui");
const base = process.env.NEUROTWIN_BASE_URL || "http://127.0.0.1:8140";
const password = fs
  .readFileSync(path.join(root, ".env"), "utf8")
  .split(/\r?\n/)
  .find((s) => s.startsWith("DEMO_PASSWORD="))
  .slice(14);
fs.mkdirSync(out, { recursive: true });
(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH }
      : {}),
  });
  const errors = [],
    steps = [];
  const open = async (role, desktop = false) => {
    const context = await browser.newContext({
      viewport: desktop ? { width: 1440, height: 1000 } : { width: 390, height: 844 },
    });
    const response = await context.request.post(base + "/api/login", {
      data: { username: role, password },
    });
    assert.equal(response.status(), 200);
    const page = await context.newPage();
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(base + (desktop ? "/dashboard/" : "/mobile/"));
    await page.locator(desktop ? ".topbar" : ".scope").waitFor();
    if (role !== "family")
      await page
        .locator(`[data-tab="${desktop ? "patient" : "check"}"]:visible`)
        .first()
        .click();
    return { context, page };
  };
  const load = async (page) => {
    const panel = page.locator(".research-panel");
    if ((await panel.getAttribute("open")) === null) await panel.locator("summary").first().click();
    await panel.locator("[data-research-load]").click();
    await page.waitForFunction(
      () =>
        document.querySelector("[data-research-status]")?.textContent ===
        "Saved records are up to date.",
    );
  };
  const settled = async (page) =>
    page.waitForFunction(
      () =>
        document.querySelector("[data-research-status]")?.textContent ===
          "Saved records are up to date." && !document.querySelector(".research-panel[aria-busy]"),
    );
  try {
    const clinician = await open("clinician", true),
      patient = await open("participant");
    const c = clinician.page,
      p = patient.page;
    await load(c);
    await c.getByRole("button", { name: "Assign synthetic workflow", exact: true }).click();
    await c.locator(".research-session").waitFor();
    await settled(c);
    assert.equal(await c.locator("[data-research-consent]").count(), 0);
    steps.push("Clinician assigns a synthetic session without proxy consent");
    await load(p);
    await p.screenshot({ path: path.join(out, "consent.png"), fullPage: true });
    await p.getByRole("button", { name: "Agree and start workflow", exact: true }).click();
    assert.equal(await p.locator("[data-research-complete]").count(), 0);
    await p.locator('[name="agree"]').check();
    await p.getByRole("button", { name: "Agree and start workflow", exact: true }).click();
    await p.locator("[data-research-complete]").waitFor();
    await settled(p);
    await p.setViewportSize({ width: 320, height: 844 });
    assert.equal(
      await p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
      false,
    );
    await p.screenshot({ path: path.join(out, "active.png"), fullPage: true });
    await p.setViewportSize({ width: 390, height: 844 });
    steps.push(
      "Consent requires a deliberate checked choice and activates only the synthetic workflow",
    );
    await p.getByRole("button", { name: "Save workflow completion", exact: true }).click();
    assert.equal(await p.locator("[data-research-complete]").count(), 1);
    await p.locator('[name="quality"]').selectOption("poor");
    await p.locator('[name="mode"]').selectOption("assisted");
    await p.locator('[name="device_class"]').selectOption("phone");
    await p.getByRole("button", { name: "Save workflow completion", exact: true }).click();
    await p.getByRole("heading", { name: "Workflow completed", exact: true }).waitFor();
    await settled(p);
    assert.match(await p.locator(".research-session").innerText(), /Declared quality: poor/);
    steps.push("Required declared provenance is stored; poor quality produces no medical score");
    p.once("dialog", (dialog) => dialog.dismiss());
    await p.getByRole("button", { name: "Withdraw consent", exact: true }).click();
    assert.equal(
      await p.getByRole("heading", { name: "Workflow completed", exact: true }).count(),
      1,
    );
    p.once("dialog", (dialog) => dialog.accept());
    await p.getByRole("button", { name: "Withdraw consent", exact: true }).click();
    await p.getByRole("heading", { name: "Consent withdrawn", exact: true }).waitFor();
    await settled(p);
    assert.equal(await p.locator("[data-research-complete]").count(), 0);
    await load(c);
    await c.getByRole("heading", { name: "Consent withdrawn", exact: true }).waitFor();
    steps.push(
      "Withdrawal requires confirmation, stops further capture and is visible to the clinician",
    );
    for (const width of [320, 390, 768, 1440]) {
      await p.setViewportSize({ width, height: 1000 });
      assert.equal(
        await p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
        false,
      );
    }
    await p.setViewportSize({ width: 320, height: 1000 });
    await p.evaluate(() => (document.documentElement.style.fontSize = "32px"));
    assert.equal(
      await p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
      false,
    );
    await p.screenshot({ path: path.join(out, "participant-large.png"), fullPage: true });
    steps.push("Research panel reflows at phone/tablet/desktop widths and enlarged text");
    await p.evaluate(() => (document.documentElement.style.fontSize = ""));
    await p.setViewportSize({ width: 390, height: 844 });
    await p.screenshot({ path: path.join(out, "participant.png"), fullPage: true });
    await c.screenshot({ path: path.join(out, "clinician.png"), fullPage: true });
    const family = await open("family");
    assert.equal(await family.page.locator(".research-panel").count(), 0);
    assert.equal(
      (
        await family.context.request.get(base + "/api/patients/patient-demo/research/sessions")
      ).status(),
      403,
    );
    steps.push("Family has neither a research panel nor API access");
    await p.route("**/research/sessions", async (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Synthetic test interruption" }),
      }),
    );
    await p.locator("[data-research-load]").click();
    await p.getByText(/Synthetic test interruption/).waitFor();
    await p.unroute("**/research/sessions");
    await load(p);
    steps.push("A failed refresh reports the failure and allows recovery");
    await p.route("**/research/sessions", (route) =>
      route.fulfill({
        status: 403,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Access not granted" }),
      }),
    );
    await p.locator("[data-research-load]").click();
    await p.getByText(/Access not granted/).waitFor();
    assert.equal(await p.locator(".research-session").count(), 0);
    await p.unroute("**/research/sessions");
    await load(p);
    steps.push("Denied access clears previously loaded research content and action controls");
    let release;
    const barrier = new Promise((resolve) => (release = resolve));
    await p.route("**/research/sessions", async (route) => {
      await barrier;
      await route.continue();
    });
    await p.locator("[data-research-load]").click();
    await p.locator('[data-tab="home"]:visible').first().click();
    release();
    await p.waitForTimeout(350);
    assert.equal(await p.locator(".research-panel").count(), 0);
    assert.equal(await p.locator(".home-heading").count(), 1);
    steps.push("A delayed response cannot insert research content into a page navigated away from");
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      path.join(out, "report.json"),
      JSON.stringify({ at: new Date().toISOString(), steps, errors }, null, 2),
    );
    console.log(JSON.stringify({ passed: steps.length, steps, errors }, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
