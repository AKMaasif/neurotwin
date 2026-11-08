// Isolated synthetic workflow. Never target an enrolled patient database.
const { chromium } = require("playwright");
const fs = require("fs"),
  path = require("path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, ".."),
  out = path.join(root, "test-results", "assessment-ui");
const base = process.env.NEUROTWIN_BASE_URL;
if (!base || base === "http://127.0.0.1:8140") throw Error("Use the isolated browser runner");
const password = fs
  .readFileSync(path.join(root, ".env"), "utf8")
  .split(/\r?\n/)
  .find((s) => s.startsWith("DEMO_PASSWORD="))
  .slice(14);
fs.mkdirSync(out, { recursive: true });
const wait = async (page, fn) => {
  const end = Date.now() + 20000;
  while (Date.now() < end) {
    if (await page.evaluate(fn)) return;
    await page.waitForTimeout(75);
  }
  throw Error("Assessment UI did not settle");
};
(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH }
      : {}),
  });
  const errors = [],
    checks = [];
  async function open(role, desktop = false) {
    const context = await browser.newContext({
      viewport: desktop ? { width: 1440, height: 1000 } : { width: 390, height: 844 },
      reducedMotion: "reduce",
    });
    const login = await context.request.post(base + "/api/login", {
      data: { username: role, password },
    });
    assert.equal(login.status(), 200);
    const page = await context.newPage();
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(base + (desktop ? "/dashboard/" : "/mobile/"));
    await page.locator(desktop ? ".topbar" : ".scope").waitFor();
    if (role !== "family")
      await page
        .locator(`[data-tab="${desktop ? "patient" : "check"}"]:visible`)
        .first()
        .click();
    return { page, context };
  }
  const settled = (page) =>
    wait(
      page,
      () =>
        document.querySelector("[data-assessment-status]")?.textContent ===
          "Activities are up to date." && !document.querySelector(".assessment-panel[aria-busy]"),
    );
  const refresh = async (page) => {
    await page.locator("[data-assessment-refresh]").click();
    await settled(page);
  };
  try {
    const c = await open("clinician", true),
      p = await open("participant"),
      f = await open("family");
    await settled(c.page);
    await settled(p.page);
    const cp = c.page,
      pp = p.page;
    await cp.getByText("Assign research activities", { exact: true }).first().click();
    await cp.locator('[name="location"]').fill("Dubai");
    await cp.locator("[data-assessment-assign] input[type=checkbox]").check();
    await cp.locator("[data-assessment-assign] button").click();
    await settled(cp);
    await refresh(pp);
    assert.equal(await pp.locator("[data-assessment-consent]").count(), 1);
    assert.equal(await f.page.locator(".assessment-panel").count(), 0);
    assert.equal(
      (await f.context.request.get(base + "/api/patients/patient-demo/assessments")).status(),
      403,
    );
    checks.push("Clinician assignment; participant consent; family isolation");
    for (const width of [320, 390, 768, 1440]) {
      await pp.setViewportSize({ width, height: 1000 });
      assert.equal(
        await pp.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
        false,
      );
    }
    await pp.setViewportSize({ width: 320, height: 1000 });
    await pp.evaluate(() => (document.documentElement.style.fontSize = "32px"));
    assert.equal(
      await pp.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
      false,
    );
    await pp.screenshot({ path: path.join(out, "consent-320-large.png"), fullPage: true });
    await pp.evaluate(() => (document.documentElement.style.fontSize = ""));
    await pp.setViewportSize({ width: 390, height: 844 });
    const consent = pp.locator("[data-assessment-consent]");
    await consent.locator('input[type="checkbox"]').nth(0).check();
    await consent.locator('input[type="checkbox"]').nth(1).check();
    await consent.locator('[name="mode"]').selectOption("self");
    await consent.locator('[name="device_class"]').selectOption("phone");
    await consent.locator("button").click();
    await settled(pp);
    const answers = {
      attention_j: ["JAZZ"],
      attention_fruit: ["BANANA", "ORANGE"],
      attention_number: ["1239"],
      memory_phrase: ["CLOSE YOUR EYES"],
      memory_j: ["JAZZ"],
      memory_number: ["1239"],
      location: ["Dubai"],
      recall: ["APPLE", "CAR", "HOUSE", "PEN", "TIE"],
      math_spent: ["67"],
      math_left: ["33"],
      visual_1: ["1", "5"],
      visual_2: ["2", "6"],
      visual_3: ["3", "6"],
      visual_4: ["3", "4"],
      trails_a: ["1", "2", "3", "4", "5"],
      trails_b: ["1", "A", "2", "B", "3", "C", "4", "D"],
    };
    const localDate = new Date(new Date().toLocaleString("en-US", { timeZone: "Asia/Dubai" }));
    answers.month = [localDate.toLocaleString("en-US", { month: "long" })];
    answers.year = [String(localDate.getFullYear())];
    answers.weekday = [localDate.toLocaleString("en-US", { weekday: "long" })];
    for (let index = 0; index < 22; index++) {
      const state = await p.context.request.get(base + "/api/patients/patient-demo/assessments");
      const row = (await state.json()).sessions[0];
      assert.equal("score" in row.payload, false);
      assert.equal("steps" in row.payload, false);
      const step = row.payload.current_step;
      assert.equal("answer" in step, false);
      await pp.locator("[data-assessment-begin]").click();
      await settled(pp);
      if (step.kind === "learning")
        await pp.waitForFunction(
          () => !document.querySelector("[data-answer-save]")?.disabled,
          {},
          { timeout: 20000 },
        );
      else if (step.kind === "stroop") {
        for (let n = 0; n < 15; n++) {
          const color = step.trials[n].color;
          await pp.locator(`[data-color="${color}"]`).click();
        }
      } else if (["text", "number"].includes(step.kind))
        await pp.locator("[data-answer-input]").fill(answers[step.id][0]);
      else if (step.kind !== "ack")
        for (const value of answers[step.id]) await pp.locator(`[data-choice="${value}"]`).click();
      if (step.id === "visual_1")
        await pp.screenshot({ path: path.join(out, "visual-activity.png"), fullPage: true });
      await pp.locator("[data-answer-save]").click();
      await settled(pp);
    }
    await pp.locator('[data-assessment-finish] [name="quality"]').selectOption("usable");
    await pp.locator("[data-assessment-finish] button").click();
    await settled(pp);
    assert.match(
      await pp.locator(".assessment-session").innerText(),
      /Waiting for care-team review/,
    );
    checks.push(
      "All 22 sequential screens, 20 scored items, timed presentation and private participant projection",
    );
    await refresh(cp);
    assert.match(await cp.locator(".assessment-session").innerText(), /30 \/ 30/);
    const review = cp.locator("[data-assessment-review]");
    await review
      .locator('input[type="checkbox"]')
      .evaluateAll((inputs) => inputs.forEach((i) => i.click()));
    await review.locator('[name="outcome"]').selectOption("reviewed_research");
    await review
      .locator('[name="rationale"]')
      .fill("All evidence and quality checks were reviewed using synthetic data.");
    await review
      .locator('[name="participant_note"]')
      .fill("Thank you. Your research activities have been reviewed by the care team.");
    await review.locator("button").click();
    await settled(cp);
    await refresh(pp);
    assert.match(
      await pp.locator(".assessment-session").innerText(),
      /Your research activities have been reviewed/,
    );
    assert.equal(await pp.locator("[data-item-points]").count(), 0);
    await cp.screenshot({ path: path.join(out, "reviewed-desktop.png"), fullPage: true });
    checks.push("Attributed clinician review; participant receives only plain-language note");
    pp.once("dialog", (dialog) => dialog.accept());
    await pp.locator('[data-assessment-action="withdraw"]').click();
    await settled(pp);
    assert.match(await pp.locator(".assessment-session").innerText(), /Consent withdrawn/);
    checks.push("Withdrawal removes reviewed result from participant use");
    await refresh(cp);
    await cp.getByText("Assign research activities", { exact: true }).first().click();
    await cp.locator('[name="location"]').fill("Dubai");
    await cp.locator("[data-assessment-assign] input[type=checkbox]").check();
    await cp.locator("[data-assessment-assign] button").click();
    await settled(cp);
    await refresh(pp);
    const second = pp.locator("[data-assessment-consent]");
    await second.locator('input[type="checkbox"]').nth(0).check();
    await second.locator('input[type="checkbox"]').nth(1).check();
    await second.locator('[name="mode"]').selectOption("self");
    await second.locator('[name="device_class"]').selectOption("phone");
    await second.locator("button").click();
    await settled(pp);
    await pp.locator("[data-assessment-begin]").click();
    await settled(pp);
    await pp.locator('[data-tab="home"]:visible').first().click();
    await pp.locator('[data-tab="check"]:visible').first().click();
    await settled(pp);
    assert.equal(await pp.locator("[data-answer-save]").count(), 0);
    assert.match(await pp.locator(".assessment-panel").innerText(), /cannot be replayed/);
    await pp.locator('[data-assessment-action="interrupt"]').click();
    await settled(pp);
    assert.match(await pp.locator(".assessment-panel").innerText(), /Session stopped/);
    checks.push("Navigation interruption blocks activity replay and preserves explicit Stop");
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      path.join(out, "report.json"),
      JSON.stringify({ checks, console_errors: errors, clinical_validation: false }, null, 2),
    );
    console.log(JSON.stringify({ passed: checks.length, console_errors: errors }));
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
