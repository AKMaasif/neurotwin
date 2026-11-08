const { chromium } = require("playwright");
const fs = require("fs"),
  path = require("path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, ".."),
  out = path.join(root, "test-results", "care-export");
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
  const steps = [],
    errors = [];
  const open = async (role) => {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 844 },
      acceptDownloads: true,
    });
    assert.equal(
      (
        await ctx.request.post(base + "/api/login", { data: { username: role, password } })
      ).status(),
      200,
    );
    const p = await ctx.newPage();
    p.on("pageerror", (e) => errors.push(e.stack || e.message));
    await p.goto(base + "/mobile/");
    await p.locator(".scope").waitFor();
    await p.locator('[data-tab="settings"]:visible').first().click();
    return { p, ctx };
  };
  try {
    const { p } = await open("participant");
    let requests = 0,
      downloads = 0;
    p.on("request", (r) => {
      if (r.url().endsWith("/care-summary/export")) requests++;
    });
    p.on("download", () => downloads++);
    p.once("dialog", (d) => d.dismiss());
    await p.locator("[data-care-export]").click();
    assert.equal(requests, 0);
    assert.equal(downloads, 0);
    steps.push("Cancelled confirmation sends no export request and creates no file");
    const waitDownload = p.waitForEvent("download");
    p.once("dialog", (d) => d.accept());
    await p.locator("[data-care-export]").click();
    const download = await waitDownload;
    assert.equal(download.suggestedFilename(), "neurotwin-care-summary.json");
    const file = await download.path();
    const content = JSON.parse(fs.readFileSync(file, "utf8"));
    assert.equal(content.schema_version, "neurotwin.care-summary.v1");
    assert.equal(content.patient.id, "patient-demo");
    assert(content.records.some((r) => r.id === "plan-demo"));
    assert(content.scope.excluded.includes("messages and attachments"));
    assert.equal(content.clinical_validation, false);
    await p.locator(".care-export").screenshot({ path: path.join(out, "export-panel.png") });
    steps.push(
      "Confirmed download contains the actual approved care projection and explicit exclusions",
    );
    await p.route("**/care-summary/export", (route) =>
      route.fulfill({ status: 403, json: { detail: "Access not granted" } }),
    );
    p.once("dialog", (d) => d.accept());
    await p.locator("[data-care-export]").click();
    await p
      .locator("[data-care-export-status]")
      .filter({ hasText: "Access not granted" })
      .waitFor();
    assert.equal(downloads, 1);
    assert.equal(await p.locator("[data-care-export]").isEnabled(), true);
    await p.unroute("**/care-summary/export");
    steps.push("Denied permission produces no download and allows an explicit retry");
    await p.route("**/care-summary/export", (route) =>
      route.fulfill({ status: 503, json: { detail: "Synthetic export service interruption" } }),
    );
    p.once("dialog", (d) => d.accept());
    await p.locator("[data-care-export]").click();
    await p
      .locator("[data-care-export-status]")
      .filter({ hasText: "Synthetic export service interruption" })
      .waitFor();
    await p.unroute("**/care-summary/export");
    const retry = p.waitForEvent("download");
    p.once("dialog", (d) => d.accept());
    await p.locator("[data-care-export]").click();
    await retry;
    steps.push("Service failure is shown honestly and a confirmed retry succeeds");
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
    await p.screenshot({ path: path.join(out, "settings-large.png"), fullPage: true });
    await p.evaluate(() => (document.documentElement.style.fontSize = ""));
    steps.push("Export description and controls reflow across widths and enlarged text");
    const before = downloads;
    let release;
    const barrier = new Promise((resolve) => (release = resolve));
    await p.route("**/care-summary/export", async (route) => {
      const response = await route.fetch();
      await barrier;
      await route.fulfill({ response });
    });
    p.once("dialog", (d) => d.accept());
    await p.locator("[data-care-export]").click();
    await p.locator('[data-tab="home"]:visible').first().click();
    release();
    await p.waitForTimeout(350);
    assert.equal(downloads, before);
    steps.push("A late export response cannot trigger a download after leaving Settings");
    const family = await open("family");
    assert.equal(await family.p.locator(".care-export").count(), 0);
    const session = await family.ctx.request.get(base + "/api/session");
    assert.equal(
      (
        await family.ctx.request.post(base + "/api/patients/patient-demo/care-summary/export", {
          headers: { "X-CSRF-Token": (await session.json()).csrf },
        })
      ).status(),
      403,
    );
    steps.push("Family has no care-summary download control or endpoint permission");
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      path.join(out, "report.json"),
      JSON.stringify({ at: new Date().toISOString(), steps, errors }, null, 2),
    );
    console.log(JSON.stringify({ passed: steps.length, steps, errors }, null, 2));
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
