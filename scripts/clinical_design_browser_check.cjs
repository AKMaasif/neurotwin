const { chromium } = require("playwright");
const fs = require("fs"),
  path = require("path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, ".."),
  out = path.join(root, "test-results", "clinical-design");
fs.mkdirSync(out, { recursive: true });
const base = process.env.NEUROTWIN_BASE_URL || "http://127.0.0.1:8140";
const password = fs
  .readFileSync(path.join(root, ".env"), "utf8")
  .split(/\r?\n/)
  .find((s) => s.startsWith("DEMO_PASSWORD="))
  .slice(14);
const wait = async (page, fn) => {
  const until = Date.now() + 20000;
  while (Date.now() < until) {
    if (await page.evaluate(fn)) return;
    await page.waitForTimeout(100);
  }
  throw Error("Clinical design condition timed out");
};
(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH }
      : {}),
  });
  const errors = [],
    steps = [];
  const open = async (role, mobile) => {
    const context = await browser.newContext({
      viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 },
      reducedMotion: "reduce",
    });
    const page = await context.newPage();
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(base + (mobile ? "/mobile/" : "/dashboard/"));
    if (mobile) await page.locator("[name=username]").selectOption(role);
    else await page.locator("[name=username]").fill(role);
    await page.locator("[name=password]").fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.locator(mobile ? ".scope" : ".topbar").waitFor();
    return page;
  };
  try {
    const patient = await open("participant", true);
    await patient.getByRole("button", { name: "Support", exact: true }).click();
    const label = "Synthetic design review " + Date.now();
    await patient.locator("#concern textarea").fill(label);
    await patient.locator("#concern button").click();
    await patient.getByText("Concern saved for clinician review.", { exact: true }).waitFor();
    await patient.locator("#concern textarea").fill("Synthetic sudden-change design " + Date.now());
    await patient.locator("#concern [name=urgent]").check();
    await patient.locator("#concern button").click();
    await patient
      .getByText("Concern recorded. Do not wait for this app for urgent assistance.", {
        exact: true,
      })
      .waitFor();
    const doctor = await open("clinician", false);
    await doctor.locator(".clinical-overview").waitFor();
    const expected = await doctor.evaluate(
      () =>
        S.data.records.filter((r) => r.kind === "case" && r.status === "awaiting_review").length,
    );
    assert.equal(
      Number(await doctor.locator(".clinical-workload strong").first().textContent()),
      expected,
    );
    assert.equal(await doctor.locator(".clinical-patient-spotlight .strip").count(), 0);
    await doctor.screenshot({ path: path.join(out, "overview-1440.png"), fullPage: true });
    steps.push(
      "overview counts match authorized records and remove the old decorative full-width progress strip",
    );
    await doctor.locator('[data-queue-state="urgent_handoff_required"]').click();
    await doctor.locator(".clinical-queue").waitFor();
    assert((await doctor.locator(".clinical-case-table tbody tr").count()) > 0);
    assert.equal(await doctor.locator(".state-awaiting_review").count(), 0);
    await doctor.locator("[data-case]").first().click();
    await doctor.getByRole("heading", { name: "Review evidence", exact: true }).waitFor();
    assert.equal(await doctor.locator("#review").count(), 0);
    steps.push(
      "reported urgent handoffs filter to actual records and retain the non-dispatch human-assistance boundary",
    );
    await doctor.locator('.sidebar [data-tab="queue"]').click();
    let posts = 0;
    doctor.on("request", (r) => {
      if (r.method() === "POST") posts++;
    });
    await doctor.locator("#review-filters [name=state]").selectOption("awaiting_review");
    await doctor.locator("#review-filters [name=query]").fill(label);
    await doctor.locator("#review-filters button.primary").click();
    assert.equal(await doctor.locator(".clinical-case-table [data-case]").count(), 1);
    assert.equal(await doctor.evaluate(() => S.dirty), false);
    await doctor.locator("#review-filters [name=query]").fill("nonexistent-" + Date.now());
    await doctor.locator("#review-filters button.primary").click();
    await doctor.getByText("No matching concerns", { exact: true }).waitFor();
    await doctor.locator("#clear-review-filters").click();
    assert.equal(posts, 0);
    steps.push(
      "search, review-state filtering and empty-result recovery are read-only and do not mark clinical forms dirty",
    );
    for (const width of [1440, 1024, 768]) {
      await doctor.setViewportSize({ width, height: 900 });
      assert.equal(
        await doctor.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
        false,
      );
      await doctor.screenshot({ path: path.join(out, `queue-${width}.png`), fullPage: true });
    }
    const table = doctor.locator(".clinical-case-table");
    await table.focus();
    assert.equal(await table.getAttribute("tabindex"), "0");
    await doctor.screenshot({ path: path.join(out, "queue-keyboard.png"), fullPage: true });
    steps.push(
      "1440/1024/768px queue layouts keep wide evidence inside a keyboard-accessible table scroller",
    );
    await doctor.setViewportSize({ width: 1440, height: 1000 });
    await doctor.locator("#dark").click();
    await doctor.screenshot({ path: path.join(out, "queue-dark.png"), fullPage: true });
    await doctor.locator("#review-filters [name=query]").fill(label);
    await doctor.locator("#review-filters button.primary").click();
    await doctor.locator("[data-case]").click();
    await doctor
      .locator("#review [name=rationale]")
      .fill("Synthetic review confirms the existing human decision workflow.");
    await doctor.locator("#review button").click();
    await doctor
      .getByText("Decision recorded with your authenticated identity.", { exact: true })
      .waitFor();
    await wait(doctor, () => S.data.records.find((r) => r.id === S.caseId)?.status === "reviewed");
    steps.push(
      "dark mode retains review controls and an explicit human decision still persists through the existing API",
    );
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      path.join(out, "report.json"),
      JSON.stringify({ status: "passed", steps, errors, physical_devices: false }, null, 2),
    );
    console.log(JSON.stringify({ status: "passed", steps, errors }));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack);
  process.exitCode = 1;
});
