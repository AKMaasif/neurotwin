const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const assert = require("node:assert/strict");
const base = process.env.NEUROTWIN_BASE_URL || "http://127.0.0.1:8140";
const root = path.resolve(__dirname, "..");
const out = path.join(root, "test-results");
fs.mkdirSync(out, { recursive: true });
const password = fs
  .readFileSync(path.join(root, ".env"), "utf8")
  .split(/\r?\n/)
  .find((s) => s.startsWith("DEMO_PASSWORD="))
  .slice(14);

(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH }
      : {}),
  });
  const errors = [],
    steps = [];
  let clinician;
  const open = async (role, mobile) => {
    const context = await browser.newContext({
      viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 },
    });
    const page = await context.newPage();
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(base + (mobile ? "/mobile/" : "/dashboard/"));
    if (mobile) await page.locator("[name=username]").selectOption(role);
    else await page.locator("[name=username]").fill(role);
    await page.locator("[name=password]").fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.locator("#logout").or(page.locator(".scope")).first().waitFor();
    return page;
  };
  const wait = async (page, fn) => {
    const until = Date.now() + 30000;
    while (Date.now() < until) {
      if (await page.evaluate(fn)) return;
      await page.waitForTimeout(200);
    }
    throw Error("Report condition timed out");
  };
  try {
    clinician = await open("clinician", false);
    await clinician.getByRole("button", { name: "Activity report", exact: true }).click();
    await clinician.locator("#report-create").waitFor();
    assert.equal(await clinician.evaluate(() => S.weekly.daily.length), 7);
    assert.equal(await clinician.evaluate(() => S.weekly.trend.length), 4);
    assert.equal(await clinician.evaluate(() => S.weekly.data_quality.expected_activities), null);
    steps.push("clinical weekly counts, seven dates and four independent denominators");
    await clinician.locator("#report-create [name=target]").selectOption("family");
    await clinician.getByRole("button", { name: "Create factual draft", exact: true }).click();
    await clinician.locator("#report-review").waitFor();
    const id = await clinician.evaluate(() => S.reportId);
    assert.equal(
      await clinician.evaluate(
        () => S.reportHistory.find((r) => r.id === S.reportId).snapshot.clinical,
      ),
      null,
    );
    const family = await open("family", true);
    await family.getByRole("button", { name: "Weekly summary", exact: true }).click();
    await wait(family, () => !!S.weekly);
    assert.equal(await family.locator(`[data-report="${id}"]`).count(), 0);
    steps.push("family draft projection excludes clinical details and is hidden until approval");
    // This check is intended for an AI-disabled local test instance; no paid call.
    await clinician.route("**/reports/snapshots/*/summarize", (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          detail: "Report AI unavailable; factual snapshot remains available",
        }),
      }),
    );
    await clinician.locator("#report-review textarea").fill("Private clinician-only review note.");
    await clinician.locator("#report-ai").click();
    await clinician
      .getByText("Report AI unavailable; factual snapshot remains available", { exact: true })
      .waitFor();
    assert.equal(
      await clinician.evaluate(() => S.reportHistory.find((r) => r.id === S.reportId).status),
      "draft",
    );
    assert.equal(
      await clinician.locator("#report-review textarea").inputValue(),
      "Private clinician-only review note.",
    );
    steps.push(
      "provider failure retains factual draft and leaves approval available (mocked outage)",
    );
    await clinician.locator("#report-review textarea").fill("Private clinician-only review note.");
    await clinician.getByRole("button", { name: "Confirm review", exact: true }).click();
    await wait(
      clinician,
      () => S.reportHistory.find((r) => r.id === S.reportId)?.status === "approved",
    );
    await family.getByRole("button", { name: "Load week", exact: true }).click();
    await family.locator(`[data-report="${id}"]`).waitFor();
    await family.locator(`[data-report="${id}"]`).click();
    assert.equal(
      await family.getByText("Private clinician-only review note.", { exact: true }).count(),
      0,
    );
    assert.equal(
      await family.getByRole("heading", { name: "Clinical review items", exact: true }).count(),
      0,
    );
    assert.equal(
      await family.evaluate(() => document.documentElement.scrollWidth > innerWidth),
      false,
    );
    steps.push(
      "approved recipient report is readable on mobile without private notes or horizontal overflow",
    );
    await family.screenshot({ path: path.join(out, "report-family.png"), fullPage: true });
    await clinician.screenshot({ path: path.join(out, "report-clinician.png"), fullPage: true });
    await clinician.locator("#report-create [name=target]").selectOption("");
    await clinician.getByRole("button", { name: "Create factual draft", exact: true }).click();
    await clinician.locator("#report-review").waitFor();
    const patient = await open("participant", true);
    await patient.getByRole("button", { name: "Done", exact: true }).first().click();
    await patient.getByText("Your response was saved.", { exact: true }).waitFor();
    await clinician.getByRole("button", { name: "Confirm review", exact: true }).click();
    await clinician
      .getByText("Source data changed; create a new snapshot before review", { exact: true })
      .waitFor();
    steps.push("a late activity response blocks stale approval in the browser");
    await family.locator("#report-period [name=end_date]").fill("2026-01-01");
    await family.getByRole("button", { name: "Load week", exact: true }).click();
    await wait(family, () => S.weekly?.end === "2026-01-01");
    assert.equal(await family.evaluate(() => S.weekly.denominator), 0);
    assert.equal(
      await family.evaluate(() => S.weekly.data_quality.dates_without_recorded_activities),
      7,
    );
    steps.push("empty week displays zero recorded activity and unavailable expected coverage");
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      path.join(out, "report-browser-check.json"),
      JSON.stringify(
        {
          status: "passed",
          steps,
          errors,
          ai_outage: "test double; no paid report model call",
          at: new Date().toISOString(),
        },
        null,
        2,
      ),
    );
    console.log(JSON.stringify({ status: "passed", steps, errors }));
  } catch (e) {
    if (clinician)
      await clinician.screenshot({ path: path.join(out, "report-failure.png"), fullPage: true });
    console.error("Completed checks:", steps);
    throw e;
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e.stack);
  process.exitCode = 1;
});
