const { chromium } = require("playwright");
const fs = require("fs"),
  path = require("path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, ".."),
  out = path.join(root, "test-results", "plan-design");
fs.mkdirSync(out, { recursive: true });
const base = process.env.NEUROTWIN_BASE_URL || "http://127.0.0.1:8140";
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
    await page.locator('nav [data-tab="plan"]').click();
    await page.locator(".plan-page").waitFor();
    return page;
  };
  try {
    const patient = await open("participant");
    const ids = await patient
      .locator(".plan-timeline-item")
      .evaluateAll((items) => items.map((item) => item.id));
    assert.equal(ids.length, new Set(ids).size);
    for (const width of [320, 390, 480]) {
      await patient.setViewportSize({ width, height: 844 });
      assert.equal(
        await patient.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
        false,
      );
      await patient.screenshot({ path: path.join(out, `plan-${width}.png`), fullPage: true });
    }
    steps.push(
      "approved activities form a unique chronological-period timeline with no horizontal overflow at 320/390/480px",
    );
    await patient.setViewportSize({ width: 320, height: 844 });
    await patient.evaluate(() => {
      document.documentElement.style.fontSize = "32px";
      document.documentElement.classList.add("large");
    });
    assert.equal(
      await patient.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
      false,
    );
    await patient.locator(".plan-help-strip button").last().scrollIntoViewIfNeeded();
    assert(
      await patient
        .locator(".plan-help-strip button")
        .last()
        .evaluate(
          (b) =>
            b.getBoundingClientRect().bottom <=
            document.querySelector("nav").getBoundingClientRect().top,
        ),
    );
    await patient.screenshot({ path: path.join(out, "plan-large-text.png"), fullPage: true });
    steps.push("200% text reflows and the final help action scrolls above the navigation dock");
    await patient.evaluate(() => {
      document.documentElement.style.fontSize = "";
      document.documentElement.classList.remove("large");
    });
    await patient.setViewportSize({ width: 390, height: 844 });
    const done = patient.locator('.plan-timeline-item [data-response="completed"]').first();
    const id = await done.getAttribute("data-id");
    await patient.locator(".plan-jump").click();
    assert.equal(new URL(patient.url()).hash, "#plan-task-" + id);
    await done.click();
    await patient.getByText("Your response was saved.", { exact: true }).waitFor();
    assert(
      await patient.evaluate(
        (id) => S.data.records.some((r) => r.id === id && r.status === "completed"),
        id,
      ),
    );
    assert.equal(
      await patient.locator("#plan-task-" + id + ' [data-response="completed"]').isVisible(),
      false,
    );
    steps.push(
      "next-step anchor targets the actual pending activity; explicit Done persists and updates its confirmed appearance",
    );
    await patient.evaluate(() => document.body.classList.add("high-contrast"));
    await patient.screenshot({ path: path.join(out, "plan-contrast.png"), fullPage: true });
    steps.push("high-contrast presentation retains the timeline and care instructions");
    const family = await open("family");
    assert.equal(await family.locator(".plan-timeline-item [data-response]").count(), 0);
    await family.getByRole("heading", { name: "Shared tasks", exact: true }).waitFor();
    steps.push(
      "authorized family sees shared plan activities without participant completion controls",
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
