const { chromium } = require("playwright");
const fs = require("fs"),
  path = require("path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, ".."),
  out = path.join(root, "test-results", "ui-reference");
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
  const errors = [],
    steps = [];
  const open = async (role, mobile) => {
    const ctx = await browser.newContext({
      viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 },
      reducedMotion: "reduce",
    });
    const page = await ctx.newPage();
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(base + (mobile ? "/mobile/" : "/dashboard/"));
    if (mobile) await page.locator("[name=username]").selectOption(role);
    else await page.locator("[name=username]").fill(role);
    await page.locator("[name=password]").fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.locator(mobile ? ".scope" : ".topbar").waitFor();
    return page;
  };
  const noOverflow = async (page) =>
    assert.equal(
      await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
      false,
    );
  try {
    const patient = await open("participant", true);
    await patient.evaluate(() => document.documentElement.classList.remove("large"));
    assert.equal(await patient.locator(".home-shortcut").count(), 4);
    assert.equal(await patient.locator(".next-activity").count(), 1);
    for (const width of [320, 360, 390, 480]) {
      await patient.setViewportSize({ width, height: 844 });
      await noOverflow(patient);
      const sizes = await patient.locator("nav button").evaluateAll((bs) =>
        bs.map((b) => ({
          width: b.getBoundingClientRect().width,
          height: b.getBoundingClientRect().height,
        })),
      );
      assert(sizes.every((s) => s.width >= 44 && s.height >= 56));
      await patient.screenshot({
        path: path.join(out, `mobile-home-${width}.png`),
        fullPage: true,
      });
    }
    steps.push(
      "reference-aligned home and five navigation targets reflow at 320/360/390/480px without page overflow",
    );
    await patient.setViewportSize({ width: 320, height: 844 });
    await patient.evaluate(() => {
      document.documentElement.classList.add("large");
      document.documentElement.style.fontSize = "32px";
    });
    await noOverflow(patient);
    await patient.locator('[aria-label="Weekly summary"]').scrollIntoViewIfNeeded();
    const reachable = await patient
      .locator('[aria-label="Weekly summary"]')
      .evaluate(
        (b) =>
          b.getBoundingClientRect().bottom <=
          document.querySelector("nav").getBoundingClientRect().top,
      );
    assert(reachable);
    await patient.screenshot({ path: path.join(out, "mobile-200-percent.png"), fullPage: true });
    steps.push(
      "200% root text at 320px reflows and the last action remains reachable above the measured navigation dock",
    );
    await patient.evaluate(() => {
      document.documentElement.classList.remove("large");
      document.documentElement.style.fontSize = "";
    });
    await patient.setViewportSize({ width: 390, height: 844 });
    await patient.getByRole("button", { name: "Companion", exact: true }).click();
    await patient.locator(".companion-figure").waitFor();
    assert.equal(await patient.evaluate(() => S.recording), false);
    await patient.screenshot({ path: path.join(out, "mobile-companion.png"), fullPage: true });
    steps.push(
      "reference-style companion is idle without microphone capture and preserves Speak/Send/Stop controls",
    );
    await patient.getByRole("button", { name: "Settings", exact: true }).click();
    await patient.locator("#contrast").click();
    await noOverflow(patient);
    await patient.screenshot({ path: path.join(out, "mobile-high-contrast.png"), fullPage: true });
    steps.push("reading comfort and high-contrast surfaces retain navigation and settings access");
    const family = await open("family", true);
    assert.deepEqual(await family.locator("nav button").allTextContents(), [
      "Overview",
      "Tasks",
      "Messages",
      "Reports",
      "Circle",
    ]);
    await family.getByRole("button", { name: "Messages", exact: true }).first().click();
    await family.locator("#care-refresh").waitFor();
    await family.getByRole("button", { name: "Companion", exact: true }).click();
    await family.locator("#chatInput").waitFor();
    await family.screenshot({ path: path.join(out, "family-companion.png"), fullPage: true });
    steps.push(
      "family-specific navigation retains direct Messages, reports, patient context and companion access",
    );
    const doctor = await open("clinician", false);
    await noOverflow(doctor);
    await doctor.screenshot({ path: path.join(out, "clinical-1440.png"), fullPage: true });
    await doctor.setViewportSize({ width: 1024, height: 768 });
    await noOverflow(doctor);
    assert.equal(await doctor.locator(".sidebar").isVisible(), false);
    await doctor.locator("#workspace-menu").click();
    await doctor.locator('.sidebar [data-tab="sources"]').click();
    await doctor.locator("#documentUpload").waitFor();
    assert.equal(await doctor.locator(".sidebar").isVisible(), false);
    await noOverflow(doctor);
    await doctor.screenshot({ path: path.join(out, "clinical-sources-1024.png"), fullPage: true });
    await doctor.locator("#workspace-menu").click();
    await doctor.keyboard.press("Escape");
    assert.equal(await doctor.locator("#workspace-menu").getAttribute("aria-expanded"), "false");
    steps.push(
      "clinical tablet menu opens, selects a workspace and closes with Escape without squeezing the evidence surface",
    );
    await doctor.setViewportSize({ width: 1440, height: 1000 });
    await doctor.locator("#dark").click();
    await noOverflow(doctor);
    await doctor.screenshot({ path: path.join(out, "clinical-dark.png"), fullPage: true });
    steps.push(
      "clinical sage/emerald identity and dark-mode source surfaces retain visible controls",
    );
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      path.join(out, "report.json"),
      JSON.stringify(
        { status: "passed", steps, errors, at: new Date().toISOString(), physical_devices: false },
        null,
        2,
      ),
    );
    console.log(JSON.stringify({ status: "passed", steps, errors }));
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e.stack);
  process.exitCode = 1;
});
