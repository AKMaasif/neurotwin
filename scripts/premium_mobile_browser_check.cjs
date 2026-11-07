const { chromium } = require("playwright"),
  fs = require("fs"),
  path = require("path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, ".."),
  out = path.join(root, "test-results", "premium-mobile"),
  base = process.env.NEUROTWIN_BASE_URL || "http://127.0.0.1:8141";
const password = fs
  .readFileSync(path.join(root, ".env"), "utf8")
  .split(/\r?\n/)
  .find((x) => x.startsWith("DEMO_PASSWORD="))
  .slice(14);
fs.mkdirSync(out, { recursive: true });
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
    for (const role of ["participant", "family"]) {
      const ctx = await browser.newContext({
          viewport: { width: 390, height: 844 },
          reducedMotion: "reduce",
        }),
        login = await ctx.request.post(base + "/api/login", { data: { username: role, password } });
      assert.equal(login.status(), 200);
      const p = await ctx.newPage();
      p.on("pageerror", (e) => errors.push(e.message));
      await p.goto(base + "/mobile/");
      await p.locator(".scope").waitFor();
      for (const tab of [
        "home",
        "plan",
        "companion",
        "support",
        "check",
        "messages",
        "weekly",
        "settings",
      ]) {
        await p.evaluate(async (tab) => {
          S.tab = tab;
          await refresh();
        }, tab);
        if (tab === "messages") {
          await p.locator("[data-care-contact]").first().click();
          await p.locator("#care-compose textarea").waitFor();
        }
        for (const width of [320, 360, 375, 390, 430, 480, 768, 1440]) {
          await p.setViewportSize({ width, height: 900 });
          assert(
            await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
            `${role}/${tab}/${width} overflow`,
          );
        }
        await p.setViewportSize({ width: 390, height: 844 });
        await p.screenshot({ path: path.join(out, `${role}-${tab}-390.png`), fullPage: true });
        if (tab === "home" && role === "participant") {
          const expected = await p.evaluate(() => {
            const tasks = records("task").filter(
              (t) =>
                t.status !== "superseded" &&
                !t.payload.is_routine_template &&
                !t.payload.occurrence_id,
            );
            return `${tasks.filter((t) => t.status === "completed").length}/${tasks.length}`;
          });
          if (await p.locator(".activity-ring").count())
            assert.equal(await p.locator(".activity-ring strong").textContent(), expected);
        }
        if (tab === "plan") {
          if (role === "participant" && (await p.locator(".routine-details").count())) {
            await p.locator(".routine-details summary").first().click();
            await p.setViewportSize({ width: 320, height: 844 });
            assert(await p.locator(".routine-details[open] .routine-identifier").isVisible());
            assert(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
            await p.locator(".routine-details summary").first().click();
            await p.locator('[data-routine-filter="awaiting_consent"]').click();
            const shown = await p.locator("[data-routine-state]:not([hidden])").count();
            assert.equal(
              shown,
              await p.evaluate(
                () => S.routineData.routines.filter((r) => r.status === "awaiting_consent").length,
              ),
            );
            await p.locator('[data-routine-filter="all"]').click();
          }
          let writes = 0;
          const count = (r) => {
            if (r.method() === "POST") writes++;
          };
          p.on("request", count);
          await p.locator('[data-plan-filter="completed"]').click();
          assert.equal(
            await p.locator('[data-plan-filter="completed"]').getAttribute("aria-pressed"),
            "true",
          );
          assert.equal(
            await p.locator(".plan-timeline-item:not([hidden]):not(.is-confirmed)").count(),
            0,
          );
          assert.equal(writes, 0);
          p.off("request", count);
          await p.locator('[data-plan-filter="all"]').click();
          if (role === "participant" && (await p.locator("[data-consent-routine]").count())) {
            await p.locator("[data-consent-routine]").first().click();
            const form = await p.locator(".routine-consent").elementHandle();
            await p.locator(".routine-consent [name=grace_minutes]").fill("45");
            await p.locator('[data-plan-filter="pending"]').click();
            assert(await form.evaluate((e) => e.isConnected));
            assert.equal(
              await p.locator(".routine-consent [name=grace_minutes]").inputValue(),
              "45",
            );
            await p.locator('[data-plan-filter="all"]').click();
          }
          if (role === "family")
            assert.equal(await p.locator("[data-response],[data-consent-routine]").count(), 0);
        }
        if (tab === "companion") {
          assert.equal(await p.locator(".companion-shell").count(), 0);
          assert.equal(await p.locator(".companion-presence.is-recording").count(), 0);
          assert.equal(
            await p
              .locator(".companion-presence path")
              .last()
              .evaluate((e) => getComputedStyle(e).animationName),
            "none",
          );
        }
        if (tab === "settings" && role === "family")
          assert.equal(await p.locator("#memorySettings,[data-revoke-access]").count(), 0);
      }
      steps.push(
        `${role}: eight screens reviewed at eight widths; real plan filtering and role boundaries preserved`,
      );
      await ctx.close();
    }
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      path.join(out, "report.json"),
      JSON.stringify(
        { status: "passed", steps, errors, synthetic: true, live_ai_calls: false },
        null,
        2,
      ),
    );
    console.log(JSON.stringify({ status: "passed", steps }));
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e.stack);
  process.exitCode = 1;
});
