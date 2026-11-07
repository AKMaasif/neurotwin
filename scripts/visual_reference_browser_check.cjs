// Actual connected UI screenshots and first-fold checks, not a mockup generator.
const { chromium } = require("playwright"),
  fs = require("fs"),
  path = require("path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, ".."),
  out = path.join(root, "test-results", "visual-reference-v2");
const base = process.env.NEUROTWIN_BASE_URL || "http://127.0.0.1:8141";
const password = fs
  .readFileSync(path.join(root, ".env"), "utf8")
  .split(/\r?\n/)
  .find((s) => s.startsWith("DEMO_PASSWORD="))
  .slice(14);
fs.mkdirSync(out, { recursive: true });
(async () => {
  const browser = await chromium.launch({
      headless: true,
      ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH
        ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH }
        : {}),
    }),
    errors = [],
    checks = [];
  try {
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      reducedMotion: "reduce",
    });
    const login = await context.request.post(base + "/api/login", {
      data: { username: "participant", password },
    });
    assert.equal(login.status(), 200);
    const page = await context.newPage();
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(base + "/mobile/");
    await page.locator(".scope").waitFor();
    await page.evaluate(() => document.fonts.ready);
    assert(
      await page.evaluate(() =>
        [...document.fonts].some(
          (font) => font.family.includes("Neuro Inter") && font.status === "loaded",
        ),
      ),
    );
    for (const [width, height] of [
      [375, 812],
      [390, 844],
      [768, 1024],
      [1024, 768],
      [1440, 900],
      [2560, 1440],
    ]) {
      await page.setViewportSize({ width, height });
      for (const tab of ["home", "plan", "support"]) {
        await page.evaluate(async (tab) => {
          S.tab = tab;
          await refresh();
          document.activeElement?.blur();
          window.scrollTo(0, 0);
        }, tab);
        await page.waitForFunction(() =>
          [...document.querySelectorAll("#mobile-content img")].every(
            (image) => image.complete && image.naturalWidth > 0,
          ),
        );
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        if (tab === "home") {
          assert.equal(await page.locator(".home-shortcut").count(), 4);
          if (width <= 390) {
            const firstFold = await page.evaluate(() => ({
              actions: document.querySelector(".home-shortcuts").getBoundingClientRect().bottom,
              nav: document
                .querySelector('nav[aria-label="Main navigation"]')
                .getBoundingClientRect().top,
            }));
            assert(firstFold.actions <= firstFold.nav, JSON.stringify(firstFold));
          }
          assert(
            await page.locator(".hero-brain img").evaluate((image) => image.naturalWidth === 512),
          );
        } else {
          assert(
            await page
              .locator(".reference-illustration")
              .evaluate((image) => image.naturalWidth === 512),
          );
          if (width < 768)
            assert(
              await page.getByRole("button", { name: "Back to home", exact: true }).isVisible(),
            );
        }
        await page.screenshot({ path: path.join(out, `${tab}-${width}.png`), fullPage: false });
        checks.push({ tab, width, height, status: "passed" });
      }
    }
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      path.join(out, "report.json"),
      JSON.stringify(
        {
          status: "passed",
          checks,
          errors,
          font: "local Inter 4.1",
          assets: "local 512px alpha WebP",
          synthetic: true,
          at: new Date().toISOString(),
        },
        null,
        2,
      ),
    );
    console.log(
      JSON.stringify({
        status: "passed",
        checks: checks.length,
        firstFold: "four shortcuts clear the navigation at 375/390px",
        errors,
      }),
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e.stack);
  process.exitCode = 1;
});
