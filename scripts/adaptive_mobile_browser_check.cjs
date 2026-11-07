const { chromium, firefox, webkit } = require("playwright");
const fs = require("fs"),
  path = require("path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, ".."),
  out = path.join(root, "test-results", "adaptive-mobile");
const base = process.env.NEUROTWIN_BASE_URL || "http://127.0.0.1:8141";
const password = fs
  .readFileSync(path.join(root, ".env"), "utf8")
  .split(/\r?\n/)
  .find((x) => x.startsWith("DEMO_PASSWORD="))
  .slice(14);
const sizes = [
  [320, 568],
  [360, 800],
  [390, 844],
  [480, 900],
  [375, 812],
  [430, 932],
  [600, 800],
  [768, 1024],
  [1024, 768],
  [1280, 720],
  [1366, 768],
  [1440, 900],
  [1920, 1080],
  [2560, 1440],
];
fs.mkdirSync(out, { recursive: true });
async function fit(page, label) {
  const result = await page.evaluate(() => ({
    width: innerWidth,
    scroll: document.documentElement.scrollWidth,
    nav: !!document.querySelector('nav[aria-label="Main navigation"]'),
    bad: [
      ...document.querySelectorAll(
        "#mobile-content input,#mobile-content select,#mobile-content textarea,#mobile-content button",
      ),
    ]
      .filter((e) => e.getClientRects().length)
      .filter((e) => {
        let r = e.getBoundingClientRect();
        return r.left < -1 || r.right > innerWidth + 1;
      })
      .slice(0, 5)
      .map((e) => e.outerHTML.slice(0, 180)),
  }));
  assert(result.scroll <= result.width + 1, `${label}: page overflow ${JSON.stringify(result)}`);
  assert.deepEqual(result.bad, [], `${label}: clipped controls`);
  assert(result.nav);
}
(async () => {
  const report = {
    at: new Date().toISOString(),
    synthetic: true,
    physical_devices: false,
    browsers: [],
    steps: [],
    performance_claim: "No field Core Web Vitals or real-user p75 measured.",
  };
  const entries = [
    [
      "chromium",
      chromium,
      process.env.PLAYWRIGHT_EXECUTABLE_PATH
        ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH }
        : {},
    ],
    [
      "firefox",
      firefox,
      process.env.PLAYWRIGHT_FIREFOX_EXECUTABLE_PATH
        ? { executablePath: process.env.PLAYWRIGHT_FIREFOX_EXECUTABLE_PATH }
        : {},
    ],
    [
      "webkit",
      webkit,
      process.env.PLAYWRIGHT_WEBKIT_EXECUTABLE_PATH
        ? { executablePath: process.env.PLAYWRIGHT_WEBKIT_EXECUTABLE_PATH }
        : {},
    ],
    ["edge", chromium, { channel: "msedge" }],
    ["chrome", chromium, { channel: "chrome" }],
  ];
  for (const [name, type, options] of entries) {
    let browser;
    try {
      browser = await type.launch({ headless: true, ...options });
    } catch (e) {
      report.browsers.push({ name, status: "unavailable", reason: e.message.split("\n")[0] });
      continue;
    }
    const errors = [],
      results = [];
    try {
      const context = await browser.newContext({
          viewport: { width: 375, height: 812 },
          reducedMotion: "reduce",
        }),
        page = await context.newPage();
      page.on("pageerror", (e) => errors.push(e.message));
      await page.goto(base + "/mobile/");
      await page.locator("[name=password]").fill(password);
      await page.locator("#login button").click();
      await page.locator(".scope").waitFor();
      const identity = await page.evaluate(() => S.user.id);
      if (name === "chromium" && !(await page.evaluate(() => S.routineData.routines.length >= 2))) {
        const date = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
        const result = await page.evaluate(async (date) => {
          if (S.routineData.routines.length) return true;
          await api(`/patients/${S.pid}/routines`, "POST", {
            template_id: "task-01",
            template_version: 1,
            timezone: "Asia/Colombo",
            local_time: "09:00",
            weekdays: [0, 1, 2, 3, 4, 5, 6],
            start_date: date,
            end_date: date,
          });
          return true;
        }, date);
        assert(result);
        const clinician = await browser.newContext();
        const login = await clinician.request.post(base + "/api/login", {
          data: { username: "clinician", password },
        });
        const account = await login.json();
        const created = await clinician.request.post(base + "/api/patients/patient-demo/routines", {
          headers: { "X-CSRF-Token": account.csrf },
          data: {
            template_id: "task-02",
            template_version: 1,
            timezone: "Asia/Colombo",
            local_time: "15:00",
            weekdays: [0, 1, 2, 3, 4, 5, 6],
            start_date: date,
            end_date: date,
          },
        });
        assert.equal(created.status(), 200);
        await clinician.close();
      }

      for (const [width, height] of sizes) {
        await page.setViewportSize({ width, height });
        for (const key of [
          "home",
          "plan",
          "check",
          "companion",
          "support",
          "settings",
          "messages",
          "weekly",
        ]) {
          await page.evaluate(async (key) => {
            S.tab = key;
            await refresh();
          }, key);
          if (key === "messages") {
            if (!(await page.evaluate(() => !!S.care.peer)))
              await page.locator("[data-care-contact]").first().click();
            await page.locator("#care-compose textarea").waitFor();
          }
          await fit(page, `${name} ${width} ${key}`);
          assert.equal(await page.evaluate(() => S.tab), key);
          assert.equal(await page.evaluate(() => S.user.id), identity);
        }
        await page.evaluate(() => {
          S.tab = "plan";
          render();
        });
        assert.equal(
          await page
            .locator('nav[aria-label="Main navigation"] button[aria-current="page"]')
            .getAttribute("data-tab"),
          "plan",
        );
        if (width === 375 || width === 768 || width === 1440 || width === 2560)
          await page.screenshot({
            path: path.join(out, `${name}-plan-${width}.png`),
            fullPage: true,
          });
        const navTargets = await page.locator("nav button").evaluateAll((buttons) =>
          buttons.map((button) => ({
            width: button.getBoundingClientRect().width,
            height: button.getBoundingClientRect().height,
            label: button.getAttribute("aria-label"),
          })),
        );
        assert(
          navTargets.every((target) => target.width >= 44 && target.height >= 44 && target.label),
        );
        results.push({ width, height, pages: 8, status: "passed", navigation_targets_44px: true });
      }
      await page.evaluate(() => {
        S.tab = "settings";
        render();
      });
      await page.locator("#memorySettings [name=preferred_name]").fill("Unsaved resize preference");
      const input = await page.locator("#memorySettings [name=preferred_name]").elementHandle();
      for (const [width, height] of [
        [375, 812],
        [812, 375],
        [375, 812],
        [1440, 900],
        [600, 800],
      ]) {
        await page.setViewportSize({ width, height });
        assert.equal(
          await page.locator("#memorySettings [name=preferred_name]").inputValue(),
          "Unsaved resize preference",
        );
        assert(await input.evaluate((e) => e.isConnected));
        await fit(page, `${name} orientation/draft`);
      }
      // Reflow equivalent CSS viewports for desktop zoom; these are not native browser-chrome zoom.
      for (const scale of [1.25, 1.5, 2, 4]) {
        await page.setViewportSize({
          width: Math.floor(1280 / scale),
          height: Math.floor(900 / scale),
        });
        await fit(page, `${name} zoom-equivalent ${scale}`);
      }
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.locator("#nav-density").click();
      assert.equal(await page.locator("#nav-density").getAttribute("aria-expanded"), "false");
      await fit(page, name + " compact rail");
      await page.locator("#nav-density").click();
      await page.evaluate(() => (document.documentElement.style.fontSize = "200%"));
      await fit(page, name + " 200% text");
      await page.evaluate(() => (document.documentElement.style.fontSize = ""));
      await page.evaluate(() => {
        S.tab = "plan";
        render();
        document
          .querySelectorAll(".routine-row h3,.plan-spotlight h2")
          .forEach(
            (e) =>
              (e.textContent =
                "Synthetic very long activity " + "identifierwithoutspaces".repeat(10)),
          );
      });
      for (const [width, height] of [
        [320, 568],
        [768, 1024],
        [1440, 900],
      ]) {
        await page.setViewportSize({ width, height });
        await fit(page, name + " long text");
      }
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.evaluate(() => {
        S.tab = "home";
        render();
      });
      await page.locator('nav [data-tab="plan"]').focus();
      await page.keyboard.press("Enter");
      await page.locator(".plan-page").waitFor();
      assert.equal(await page.evaluate(() => S.tab), "plan");
      await page.locator('.plan-context [data-tab="support"]').click();
      await page.locator("#help").waitFor();
      await page.locator("#help [name=text]").fill("Synthetic responsive support request");
      await page.locator("#help button").click();
      await page.getByText("Help request saved in app.", { exact: true }).waitFor();
      assert.deepEqual(errors, []);
      report.browsers.push({
        name,
        version: browser.version(),
        status: "passed",
        viewports: results,
        page_errors: errors,
        draft_preserved: true,
        keyboard: true,
        reflow_equivalent_zoom: [125, 150, 200, 400],
        native_browser_zoom_tested: false,
      });
    } catch (e) {
      report.browsers.push({ name, status: "failed", error: e.message, viewports: results });
      console.error(name, e.message);
    } finally {
      await browser.close();
    }
    fs.writeFileSync(path.join(out, "report.json"), JSON.stringify(report, null, 2));
  }
  fs.writeFileSync(path.join(out, "report.json"), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
  if (
    !report.browsers.some((b) => b.status === "passed") ||
    report.browsers.some((b) => b.status === "failed")
  )
    process.exitCode = 1;
})().catch((e) => {
  console.error(e.stack);
  process.exitCode = 1;
});
