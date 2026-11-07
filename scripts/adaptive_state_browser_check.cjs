const { chromium } = require("playwright"),
  fs = require("fs"),
  path = require("path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, ".."),
  out = path.join(root, "test-results", "adaptive-mobile"),
  base = process.env.NEUROTWIN_BASE_URL || "http://127.0.0.1:8141";
const password = fs
  .readFileSync(path.join(root, ".env"), "utf8")
  .split(/\r?\n/)
  .find((x) => x.startsWith("DEMO_PASSWORD="))
  .slice(14);
async function fit(page) {
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
}
(async () => {
  const browser = await chromium.launch({
      headless: true,
      ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH
        ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH }
        : {}),
    }),
    steps = [],
    errors = [];
  try {
    const ctx = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      reducedMotion: "reduce",
    });
    await ctx.addInitScript(() => {
      window.lab = { cls: 0, lcp: null };
      new PerformanceObserver((list) => {
        for (const e of list.getEntries()) if (!e.hadRecentInput) window.lab.cls += e.value;
      }).observe({ type: "layout-shift", buffered: true });
      new PerformanceObserver((list) => {
        window.lab.lcp = list.getEntries().at(-1)?.startTime;
      }).observe({ type: "largest-contentful-paint", buffered: true });
    });
    const p = await ctx.newPage();
    p.on("pageerror", (e) => errors.push(e.message));
    await p.goto(base + "/mobile/");
    await p.locator("[name=password]").fill(password);
    await p.locator("#login button").click();
    await p.locator(".scope").waitFor();
    await p.waitForTimeout(250);
    const lab = await p.evaluate(() => ({
      ...window.lab,
      navigation_dom_ms: performance.getEntriesByType("navigation")[0].domContentLoadedEventEnd,
    }));
    await p.locator('nav [data-tab="plan"]').click();
    await p.locator("[data-consent-routine]").first().click();
    await p.locator(".routine-consent").waitFor();
    await p.locator(".routine-consent [name=grace_minutes]").fill("45");
    const form = await p.locator(".routine-consent").elementHandle();
    for (const [width, height] of [
      [320, 568],
      [375, 812],
      [768, 1024],
      [1024, 768],
      [1440, 900],
      [2560, 1440],
    ]) {
      await p.setViewportSize({ width, height });
      await fit(p);
      assert.equal(await p.locator(".routine-consent [name=grace_minutes]").inputValue(), "45");
      assert(await form.evaluate((e) => e.isConnected));
      assert.equal(await p.evaluate(() => S.tab), "plan");
    }
    await p.evaluate(() =>
      document
        .querySelectorAll(".routine-row h3,.routine-identifier")
        .forEach((e) => (e.textContent += "VeryLongUnbrokenSyntheticValue".repeat(12))),
    );
    for (const width of [320, 768, 1440]) {
      await p.setViewportSize({ width, height: 900 });
      await fit(p);
    }
    steps.push(
      "Expanded real routine controls retain entered values and DOM identity across rotation/resizing; long identifiers wrap",
    );
    await p.setViewportSize({ width: 320, height: 568 });
    await p.evaluate(() => (document.documentElement.style.fontSize = "200%"));
    await fit(p);
    await p.locator(".routine-consent button").scrollIntoViewIfNeeded();
    assert(await p.locator(".routine-consent button").isVisible());
    await p.evaluate(() => (document.documentElement.style.fontSize = ""));
    steps.push(
      "Expanded routine controls and confirmation remain reachable at 320px with 200% text",
    );
    // Simulated transport failures exercise real recovery controls, without changing backend data.
    let held, release;
    const started = new Promise((r) => (held = r)),
      gate = new Promise((r) => (release = r));
    await p.route("**/api/patients/patient-demo/workspace", async (route) => {
      const response = await route.fetch();
      held();
      await gate;
      await route.fulfill({ response });
    });
    const load = p.reload();
    await started;
    await p.getByRole("heading", { name: "Opening workspace", exact: true }).waitFor();
    await fit(p);
    release();
    await load;
    await p.locator(".scope").waitFor();
    await p.unroute("**/api/patients/patient-demo/workspace");
    steps.push(
      "Slow initial workspace response displays a bounded loading state and recovers to actual data",
    );
    await p.route(
      "**/api/patients/patient-demo/workspace",
      (route) =>
        route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Synthetic responsive recovery outage" }),
        }),
      { times: 1 },
    );
    await p.reload();
    await p.locator("#workspace-retry").waitFor();
    await fit(p);
    await p.locator("#workspace-retry").click();
    await p.locator(".scope").waitFor();
    steps.push(
      "Simulated workspace outage exposes a working refresh-access retry instead of a broken layout",
    );
    const family = await browser.newContext({
      viewport: { width: 375, height: 812 },
      hasTouch: true,
    });
    const login = await family.request.post(base + "/api/login", {
      data: { username: "family", password },
    });
    assert.equal(login.status(), 200);
    const f = await family.newPage();
    f.on("pageerror", (e) => errors.push(e.message));
    await f.goto(base + "/mobile/");
    await f.locator(".scope").waitFor();
    for (const width of [320, 600, 768, 1024, 1440, 2560]) {
      await f.setViewportSize({ width, height: 900 });
      for (const tab of ["home", "plan", "weekly", "messages", "settings", "support"]) {
        await f.evaluate(async (tab) => {
          S.tab = tab;
          await refresh();
        }, tab);
        await fit(f);
        assert.equal(await f.locator("nav button").count(), 5);
      }
    }
    await f.setViewportSize({ width: 430, height: 932 });
    await f.locator('nav [data-tab="home"]').tap();
    assert.equal(await f.evaluate(() => S.tab), "home");
    steps.push(
      "Family pages retain their five authorized navigation destinations across six widths; touch navigation works",
    );
    assert.deepEqual(errors, []);
    fs.mkdirSync(out, { recursive: true });
    fs.writeFileSync(
      path.join(out, "state-report.json"),
      JSON.stringify(
        {
          status: "passed",
          steps,
          errors,
          lab_sample: lab,
          lab_limitations:
            "Single local Chromium sample; includes login transition; not field p75, INP, Safari, physical device or performance certification.",
        },
        null,
        2,
      ),
    );
    console.log(JSON.stringify({ status: "passed", steps, lab_sample: lab }));
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e.stack);
  process.exitCode = 1;
});
