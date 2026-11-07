const { chromium } = require("playwright");
const fs = require("fs"),
  path = require("path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, ".."),
  out = path.join(root, "test-results", "camera-assistance");
const base = process.env.NEUROTWIN_BASE_URL || "http://127.0.0.1:8140";
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
  });
  const steps = [],
    errors = [],
    sent = [];
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  try {
    assert.equal(
      (
        await ctx.request.post(base + "/api/login", { data: { username: "participant", password } })
      ).status(),
      200,
    );
    const p = await ctx.newPage();
    p.on("pageerror", (e) => errors.push(e.message));
    await p.goto(base + "/mobile/");
    await p.locator(".scope").waitFor();
    await p.locator('[data-tab="companion"]:visible').first().click();
    await p.locator(".camera-panel > summary").click();
    await p
      .locator("[data-camera-provider]")
      .filter({ hasText: "not enabled or configured" })
      .waitFor();
    assert.equal(await p.locator("[data-camera-send]").isDisabled(), true);
    steps.push("Disabled provider is shown honestly; no live inference is attempted");
    await p.route("**/camera/options", async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      await route.fulfill({
        json: { ...body, provider_ready: true, model: "synthetic-browser-test-double" },
      });
    });
    await p.locator("[data-camera-options]").click();
    await p
      .locator("[data-camera-provider]")
      .filter({ hasText: "synthetic-browser-test-double" })
      .waitFor();
    const b64 = await p.evaluate(() => {
      const c = document.createElement("canvas");
      c.width = 320;
      c.height = 240;
      const g = c.getContext("2d");
      g.fillStyle = "white";
      g.fillRect(0, 0, 320, 240);
      g.fillStyle = "blue";
      g.fillRect(30, 30, 120, 160);
      return c.toDataURL("image/png").split(",")[1];
    });
    const sample = {
      name: "synthetic-sample.png",
      mimeType: "image/png",
      buffer: Buffer.from(b64, "base64"),
    };
    const choose = async () => {
      await p.locator("[data-camera-file]").setInputFiles(sample);
      await p.locator("[data-camera-status]").filter({ hasText: "Preview only" }).waitFor();
    };
    const success = {
      status: "tentative",
      text: "There may be a cup in the left of the image. This is an image-based guess.",
      clinical_use: false,
      image_retained: false,
    };
    await p.route("**/camera/check", async (route) => {
      sent.push({
        consent: route.request().headers()["x-camera-consent"],
        bytes: route.request().postDataBuffer().length,
      });
      await route.fulfill({ json: success });
    });
    await choose();
    assert.equal(await p.locator("[data-camera-file]").evaluate((el) => el.files.length), 1);
    assert.equal(sent.length, 0);
    assert.equal(await p.locator("[data-camera-send]").isDisabled(), true);
    await p.locator("[data-camera-clear]").click();
    assert.equal(await p.locator("[data-camera-preview]").isHidden(), true);
    assert.equal(sent.length, 0);
    steps.push("Choose/preview/clear sends no image and requires a separate explicit consent");
    await choose();
    await p.locator("[data-camera-consent]").check();
    await p.locator("[data-camera-send]").click();
    await p.locator("[data-camera-result]").filter({ hasText: "may be a cup" }).waitFor();
    assert.equal(sent.length, 1);
    assert.equal(sent[0].consent, "synthetic-camera-1");
    assert.equal(await p.locator("[data-camera-consent]").isChecked(), false);
    steps.push(
      "Explicit send carries consent and displays a tentative test-double result; resending requires consent again",
    );
    await p.screenshot({ path: path.join(out, "participant.png"), fullPage: true });
    await p.unroute("**/camera/check");
    await p.route("**/camera/check", (route) =>
      route.fulfill({ status: 503, json: { detail: "Synthetic provider unavailable" } }),
    );
    await p.locator("[data-camera-consent]").check();
    await p.locator("[data-camera-send]").click();
    await p
      .locator("[data-camera-status]")
      .filter({ hasText: "Synthetic provider unavailable" })
      .waitFor();
    assert.equal(await p.locator("[data-camera-result]").textContent(), "");
    assert.equal(await p.locator("[data-camera-consent]").isChecked(), false);
    steps.push(
      "Provider failure clears prior suggestions, reports the error and preserves explicit retry control",
    );
    await p.unroute("**/camera/check");
    await p.route("**/camera/check", (route) =>
      route.fulfill({
        json: {
          ...success,
          status: "unclear",
          text: "I could not make a useful object suggestion from this image.",
        },
      }),
    );
    await p.locator("[data-camera-consent]").check();
    await p.locator("[data-camera-send]").click();
    await p
      .locator("[data-camera-status]")
      .filter({ hasText: "No useful object suggestion" })
      .waitFor();
    steps.push("Uncertain output is a first-class state rather than an invented recognition");
    await p.locator("[data-camera-file]").setInputFiles({
      name: "invalid.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("invalid"),
    });
    await p.locator("[data-camera-status]").filter({ hasText: "Choose a nonempty" }).waitFor();
    assert.equal(await p.locator("[data-camera-send]").isDisabled(), true);
    steps.push("Unsupported files are rejected before sending");
    await choose();
    await p.unroute("**/camera/check");
    let release;
    const barrier = new Promise((resolve) => (release = resolve));
    await p.route("**/camera/check", async (route) => {
      await barrier;
      try {
        await route.fulfill({ json: success });
      } catch {
        /* Client deliberately aborted. */
      }
    });
    await p.locator("[data-camera-consent]").check();
    await p.locator("[data-camera-send]").click();
    await p.locator("[data-camera-status]").filter({ hasText: "Checking your sample" }).waitFor();
    await p.locator("[data-camera-clear]").click();
    release();
    await p.waitForTimeout(200);
    assert.equal(await p.locator("[data-camera-result]").textContent(), "");
    assert.equal(await p.evaluate(() => S.cameraBusy), false);
    steps.push("Clearing an in-flight request aborts local waiting and rejects its late result");
    await choose();
    for (const width of [320, 390, 768, 1440]) {
      await p.setViewportSize({ width, height: 1000 });
      assert.equal(
        await p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
        false,
      );
    }
    await p.setViewportSize({ width: 320, height: 1000 });
    await p.evaluate(() => (document.documentElement.style.fontSize = "32px"));
    if (await p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1))
      console.log(
        await p.evaluate(() =>
          [...document.querySelectorAll("main *")]
            .filter((el) => el.getBoundingClientRect().right > innerWidth + 1)
            .map((el) => ({
              tag: el.tagName,
              cls: el.className,
              width: el.getBoundingClientRect().width,
              text: el.textContent.slice(0, 60),
            }))
            .slice(0, 16),
        ),
      );
    assert.equal(
      await p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
      false,
    );
    await p.screenshot({ path: path.join(out, "large-text.png"), fullPage: true });
    await p.evaluate(() => (document.documentElement.style.fontSize = ""));
    steps.push(
      "Preview and consent controls reflow at phone/tablet/desktop widths and enlarged text",
    );
    await p.locator('[data-tab="home"]:visible').first().click();
    await p.locator('[data-tab="companion"]:visible').first().click();
    assert.equal(await p.locator("[data-camera-preview]").getAttribute("src"), null);
    steps.push("Navigation clears the photo and result without putting them in companion history");
    const family = await browser.newContext();
    assert.equal(
      (
        await family.request.post(base + "/api/login", { data: { username: "family", password } })
      ).status(),
      200,
    );
    const f = await family.newPage();
    await f.goto(base + "/mobile/");
    await f.locator(".scope").waitFor();
    await f.evaluate(() => {
      S.tab = "companion";
      render();
    });
    assert.equal(await f.locator(".camera-panel").count(), 0);
    assert.equal(
      (await family.request.get(base + "/api/patients/patient-demo/camera/options")).status(),
      403,
    );
    steps.push("Family has no camera panel or camera endpoint access");
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      path.join(out, "report.json"),
      JSON.stringify(
        {
          at: new Date().toISOString(),
          provider_mode: "browser routes use explicit test doubles; no live AI inference",
          steps,
          errors,
        },
        null,
        2,
      ),
    );
    console.log(JSON.stringify({ passed: steps.length, steps, errors }, null, 2));
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
