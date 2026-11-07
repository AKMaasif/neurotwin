const { chromium } = require("playwright");
const fs = require("fs"),
  path = require("path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, ".."),
  out = path.join(root, "test-results", "family-reports");
fs.mkdirSync(out, { recursive: true });
const base = process.env.NEUROTWIN_BASE_URL || "http://127.0.0.1:8140";
const password = fs
  .readFileSync(path.join(root, ".env"), "utf8")
  .split(/\r?\n/)
  .find((s) => s.startsWith("DEMO_PASSWORD="))
  .slice(14);
const wait = async (page, fn) => {
  const end = Date.now() + 20000;
  while (Date.now() < end) {
    if (await page.evaluate(fn)) return;
    await page.waitForTimeout(100);
  }
  throw Error("Family/report condition timed out");
};
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
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      reducedMotion: "reduce",
    });
    const page = await context.newPage();
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(base + "/mobile/");
    await page.locator("[name=username]").selectOption(role);
    await page.locator("[name=password]").fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.locator(".scope").waitFor();
    return page;
  };
  try {
    const patient = await open("participant");
    await patient.getByRole("button", { name: "Support", exact: true }).click();
    const text = "Synthetic family coordination " + Date.now();
    await patient.locator("#help [name=recipient_id]").selectOption("family");
    await patient.locator("#help textarea").fill(text);
    await patient.locator("#help button").click();
    await patient.getByText("Help request saved in app.", { exact: true }).waitFor();
    const family = await open("family");
    await family.locator(".family-overview").waitFor();
    assert(await family.locator(".family-request-card").filter({ hasText: text }).isVisible());
    assert.equal(
      Number(await family.locator(".family-attention .care-record-count").textContent()),
      await family.evaluate(
        () =>
          S.data.records.filter(
            (r) =>
              r.kind === "help" && r.payload.recipient_id === S.user.id && r.status === "requested",
          ).length,
      ),
    );
    for (const width of [320, 390, 480]) {
      await family.setViewportSize({ width, height: 844 });
      assert.equal(
        await family.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
        false,
      );
      if (width === 390)
        await family.screenshot({ path: path.join(out, "family-overview.png"), fullPage: true });
    }
    steps.push(
      "family overview prioritizes actual recipient-bound requests and reflows at 320/390/480px",
    );
    await family
      .locator(".family-request-card")
      .filter({ hasText: text })
      .getByRole("button", { name: "Accept responsibility", exact: true })
      .click();
    await family.getByText("Responsibility accepted.", { exact: true }).waitFor();
    assert.equal(await family.locator(".family-request-card").filter({ hasText: text }).count(), 0);
    await family.locator(".family-accepted-note").waitFor();
    steps.push(
      "explicit acceptance persists and removes only that request from the waiting list without claiming activity completion",
    );
    await family.setViewportSize({ width: 390, height: 844 });
    await family.getByRole("button", { name: "Weekly summary", exact: true }).click();
    await wait(family, () => !!S.weekly);
    assert.equal(
      await family.locator(".mobile-week-record").first().locator("h2 strong").textContent(),
      String(await family.evaluate(() => S.weekly.counts.completed)),
    );
    assert.equal(await family.locator(".mobile-daily-record .report-bar-row").count(), 7);
    assert.equal(await family.evaluate(() => S.weekly.clinical), null);
    assert.equal(
      await family.getByRole("heading", { name: "Clinical review items", exact: true }).count(),
      0,
    );
    await family.locator("#notice").waitFor({ state: "hidden", timeout: 10000 });
    await family.screenshot({ path: path.join(out, "weekly-report.png"), fullPage: true });
    steps.push(
      "weekly layout displays real counts and seven dated rows while excluding clinical-only evidence",
    );
    await family.setViewportSize({ width: 320, height: 844 });
    await family.evaluate(() => {
      document.documentElement.classList.add("large");
      document.documentElement.style.fontSize = "32px";
    });
    assert.equal(
      await family.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
      false,
    );
    await family.screenshot({ path: path.join(out, "weekly-large-text.png"), fullPage: true });
    await family.evaluate(() => {
      document.documentElement.classList.remove("large");
      document.documentElement.style.fontSize = "";
    });
    await family.locator("#report-period [name=end_date]").fill("2026-01-01");
    await family.getByRole("button", { name: "Load week", exact: true }).click();
    await wait(family, () => S.weekly?.end === "2026-01-01");
    assert.equal(
      await family.locator(".mobile-week-record").first().locator("h2 strong").textContent(),
      "0",
    );
    assert.equal(await family.evaluate(() => S.weekly.denominator), 0);
    assert.equal(await family.evaluate(() => S.weekly.data_quality.expected_activities), null);
    steps.push(
      "large text reflows and empty weeks stay zero-record evidence without invented adherence or expected counts",
    );
    await family.evaluate(() => document.body.classList.add("high-contrast"));
    await family.screenshot({ path: path.join(out, "weekly-contrast.png"), fullPage: true });
    const snapshots = await family.locator("[data-report]").count();
    if (snapshots) {
      await family.locator("[data-report]").first().click();
      await family.locator(".report-snapshot > summary").click();
      assert.equal(await family.locator(".report-snapshot .mobile-week-record").count(), 1);
    }
    steps.push(
      "high-contrast and approved saved-report evidence retain the recipient-safe report presentation",
    );
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      path.join(out, "report.json"),
      JSON.stringify(
        {
          status: "passed",
          steps,
          errors,
          saved_snapshot_checked: snapshots > 0,
          physical_devices: false,
        },
        null,
        2,
      ),
    );
    console.log(
      JSON.stringify({ status: "passed", steps, errors, saved_snapshot_checked: snapshots > 0 }),
    );
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack);
  process.exitCode = 1;
});
