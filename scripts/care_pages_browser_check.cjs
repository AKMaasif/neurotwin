const { chromium } = require("playwright");
const fs = require("fs"),
  path = require("path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, ".."),
  out = path.join(root, "test-results", "care-pages");
fs.mkdirSync(out, { recursive: true });
const base = process.env.NEUROTWIN_BASE_URL || "http://127.0.0.1:8140";
const password = fs
  .readFileSync(path.join(root, ".env"), "utf8")
  .split(/\r?\n/)
  .find((s) => s.startsWith("DEMO_PASSWORD="))
  .slice(14);
const wait = async (page, fn) => {
  const end = Date.now() + 15000;
  while (Date.now() < end) {
    if (await page.evaluate(fn)) return;
    await page.waitForTimeout(100);
  }
  throw Error("Care-page condition timed out");
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
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  try {
    await page.goto(base + "/mobile/");
    await page.locator("[name=username]").selectOption("participant");
    await page.locator("[name=password]").fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.locator(".scope").waitFor();
    for (const [tab, selector] of [
      ["check", ".check-page"],
      ["support", ".support-page"],
      ["settings", ".settings-page"],
    ]) {
      if (tab === "settings" && !(await page.locator('[data-tab="settings"]:visible').count()))
        await page.getByRole("button", { name: "Back to home", exact: true }).click();
      await page.locator(`[data-tab="${tab}"]:visible`).first().click();
      await page.locator(selector).waitFor();
      await page.evaluate(() => document.documentElement.classList.remove("large"));
      for (const width of [320, 390, 480]) {
        await page.setViewportSize({ width, height: 844 });
        assert.equal(
          await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
          false,
        );
        if (width === 390)
          await page.screenshot({ path: path.join(out, tab + ".png"), fullPage: true });
      }
      await page.setViewportSize({ width: 320, height: 844 });
      await page.evaluate(() => {
        document.documentElement.style.fontSize = "32px";
        document.documentElement.classList.add("large");
      });
      assert.equal(
        await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
        false,
      );
      const last = page.locator("main button").last();
      await last.scrollIntoViewIfNeeded();
      assert(
        await last.evaluate(
          (b) =>
            b.getBoundingClientRect().bottom <=
            document.querySelector("nav").getBoundingClientRect().top,
        ),
      );
      await page.screenshot({ path: path.join(out, tab + "-large.png"), fullPage: true });
      await page.evaluate(() => {
        document.documentElement.style.fontSize = "";
        document.documentElement.classList.remove("large");
      });
    }
    steps.push(
      "Support, Settings and My Check reflow at 320/390/480px and 200% text, with reachable final actions",
    );
    await page.setViewportSize({ width: 390, height: 844 });
    const memory = page.locator("#memorySettings [name=preferred_name]");
    await memory.fill("Synthetic unsaved choice");
    await page.locator("#contrast").click();
    assert.equal(await page.locator("#contrast").getAttribute("aria-pressed"), "true");
    assert.equal(await memory.inputValue(), "Synthetic unsaved choice");
    await page.screenshot({ path: path.join(out, "settings-contrast.png"), fullPage: true });
    await page.locator("#contrast").click();
    steps.push(
      "contrast pressed state matches appearance and does not discard unsaved privacy-form input",
    );
    await page.locator("#size").click();
    await wait(page, () => document.documentElement.classList.contains("large") === true);
    assert.equal(await page.locator("#size").getAttribute("aria-pressed"), "true");
    await page.reload();
    await page.locator(".scope").waitFor();
    assert(await page.evaluate(() => document.documentElement.classList.contains("large")));
    steps.push("text-size preference is saved through the backend and survives a reload");
    await page.getByRole("button", { name: "My Check", exact: true }).click();
    await page.getByText("NOT AVAILABLE IN THIS BUILD", { exact: true }).waitFor();
    assert.equal(
      await page.getByRole("button", { name: /start assessment|begin test/i }).count(),
      0,
    );
    await page.getByRole("button", { name: "Report a concern", exact: true }).click();
    await page.locator("#concern").waitFor();
    steps.push(
      "assessment screen offers no fake test or score and routes concerns to the working support form",
    );
    const expected = await page.evaluate(() => S.contacts.map((c) => c.name));
    assert.deepEqual(await page.locator(".care-contact-list strong").allTextContents(), expected);
    await page.locator('a[href="#practical-help"]').click();
    assert.equal(new URL(page.url()).hash, "#practical-help");
    const text = "Synthetic practical support " + Date.now();
    await page.locator("#help textarea").fill(text);
    await page.locator("#help button").click();
    await page.getByText("Help request saved in app.", { exact: true }).waitFor();
    assert(
      await page.evaluate(
        (text) => S.data.records.some((r) => r.kind === "help" && r.payload.text === text),
        text,
      ),
    );
    steps.push(
      "contact list reflects authorized server contacts and explicit support submission persists with a truthful receipt",
    );
    await page.locator("#concern textarea").fill("Synthetic non-urgent concern " + Date.now());
    await page.locator("#concern button").click();
    await page.getByText("Concern saved for clinician review.", { exact: true }).waitFor();
    steps.push("care-team concern form retains its real review workflow and emergency boundaries");
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
