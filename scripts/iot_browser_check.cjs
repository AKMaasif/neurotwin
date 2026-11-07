const { chromium } = require("playwright");
const fs = require("fs"),
  path = require("path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, ".."),
  out = path.join(root, "test-results", "iot-simulation");
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
    errors = [];
  const open = async (role, desktop = false) => {
    const ctx = await browser.newContext({
      viewport: desktop ? { width: 1440, height: 1000 } : { width: 390, height: 844 },
    });
    assert.equal(
      (
        await ctx.request.post(base + "/api/login", { data: { username: role, password } })
      ).status(),
      200,
    );
    const p = await ctx.newPage();
    p.on("pageerror", (e) => errors.push(e.message));
    await p.goto(base + (desktop ? "/dashboard/" : "/mobile/"));
    await p.locator(desktop ? ".topbar" : ".scope").waitFor();
    if (role !== "family")
      await p
        .locator(`[data-tab="${desktop ? "patient" : "check"}"]:visible`)
        .first()
        .click();
    return { p, ctx };
  };
  const ready = async (p) =>
    p.waitForFunction(
      () =>
        !document.querySelector(".iot-panel[aria-busy]") &&
        document
          .querySelector("[data-iot-status]")
          ?.textContent.startsWith("Saved simulation records loaded"),
    );
  const load = async (p) => {
    const panel = p.locator(".iot-panel");
    if ((await panel.getAttribute("open")) === null) await panel.locator("summary").click();
    await p.locator("[data-iot-load]").click();
    await ready(p);
  };
  const inject = async (p, kind, { value, gap = 0 } = {}) => {
    await p.locator('[data-iot-inject] [name="kind"]').selectOption(kind);
    if (value !== undefined)
      await p.locator('[data-iot-inject] [name="value"]').fill(String(value));
    await p.locator('[data-iot-inject] [name="gap"]').fill(String(gap));
    await p.getByRole("button", { name: "Inject labelled test event", exact: true }).click();
  };
  try {
    const { p: c } = await open("clinician", true),
      { p } = await open("participant");
    await load(c);
    assert.equal(await c.locator("[data-iot-inject]").count(), 0);
    await load(p);
    await p.getByRole("button", { name: "Allow device simulation", exact: true }).click();
    assert.equal(await p.locator("[data-iot-withdraw]").count(), 0);
    await p.locator('[data-iot-permission] [type="checkbox"]').check();
    await p.getByRole("button", { name: "Allow device simulation", exact: true }).click();
    await p.locator("[data-iot-withdraw]").waitFor();
    await ready(p);
    steps.push("Participant must explicitly allow simulation; clinician cannot inject beforehand");
    await load(c);
    await inject(c, "connected");
    await ready(c);
    await inject(c, "reading", { value: 0 });
    await ready(c);
    assert.match(
      await c.locator("[data-iot-content]").innerText(),
      /Simulated activity count: 0 count/,
    );
    steps.push(
      "Connected synthetic stream persists a zero-valued activity count with simulation provenance",
    );
    await inject(c, "disconnected");
    await ready(c);
    await inject(c, "reading", { value: 4 });
    await c
      .locator("[data-iot-status]")
      .filter({ hasText: "Readings require an explicitly connected simulation" })
      .waitFor();
    await load(c);
    await inject(c, "missing_reading", { gap: 2 });
    await ready(c);
    assert.match(
      await c.locator("[data-iot-content]").innerText(),
      /Simulated connection:\s*disconnected/,
    );
    assert.match(await c.locator("[data-iot-content]").innerText(), /gap 2/);
    steps.push("Disconnect rejects readings; missing readings and sequence gaps stay explicit");
    await inject(c, "fault");
    await ready(c);
    assert.match(
      await c.locator("[data-iot-content]").innerText(),
      /Simulated connection:\s*faulted/,
    );
    await inject(c, "connected");
    await ready(c);
    await inject(c, "reading", { value: 2 });
    await ready(c);
    steps.push(
      "Fault and reconnection allow new readings without fabricating replacement measurements",
    );
    await inject(c, "review_signal");
    await ready(c);
    await c.getByRole("button", { name: "Acknowledge test signal", exact: true }).click();
    await ready(c);
    assert.equal(await c.locator("[data-iot-review]").count(), 0);
    assert.match(await c.locator("[data-iot-content]").innerText(), /reviewed · acknowledged/);
    steps.push("Test review signal needs an explicit recorded clinician decision");
    p.once("dialog", (d) => d.accept());
    await p.locator("[data-iot-withdraw]").click();
    await p
      .locator("[data-iot-status]")
      .filter({ hasText: "Simulation permission changed" })
      .waitFor();
    await load(p);
    p.once("dialog", (d) => d.dismiss());
    await p.locator("[data-iot-withdraw]").click();
    assert.equal(await p.locator("[data-iot-withdraw]").count(), 1);
    p.once("dialog", (d) => d.accept());
    await p.locator("[data-iot-withdraw]").click();
    await ready(p);
    await load(c);
    assert.equal(await c.locator("[data-iot-inject]").count(), 0);
    steps.push(
      "Stale permission changes are rejected; confirmed withdrawal stops injection and retains history",
    );
    const family = await open("family");
    assert.equal(await family.p.locator(".iot-panel").count(), 0);
    assert.equal(
      (await family.ctx.request.get(base + "/api/patients/patient-demo/iot-simulation")).status(),
      403,
    );
    steps.push("Family receives neither simulator controls nor endpoint access");
    for (const width of [320, 390, 768, 1440]) {
      await p.setViewportSize({ width, height: 1000 });
      assert.equal(
        await p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
        false,
      );
    }
    await p.setViewportSize({ width: 320, height: 1000 });
    await p.evaluate(() => (document.documentElement.style.fontSize = "32px"));
    assert.equal(
      await p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
      false,
    );
    await p.screenshot({ path: path.join(out, "participant-large.png"), fullPage: true });
    await p.evaluate(() => (document.documentElement.style.fontSize = ""));
    await p.setViewportSize({ width: 390, height: 844 });
    await p.screenshot({ path: path.join(out, "participant.png"), fullPage: true });
    await c.screenshot({ path: path.join(out, "clinician.png"), fullPage: true });
    steps.push("Participant history reflows across phone/tablet/desktop and enlarged text");
    await p.route("**/iot-simulation?*", (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Synthetic service interruption" }),
      }),
    );
    await p.locator("[data-iot-load]").click();
    await p
      .locator("[data-iot-status]")
      .filter({ hasText: "Synthetic service interruption" })
      .waitFor();
    await p.unroute("**/iot-simulation?*");
    await load(p);
    steps.push("Interrupted loads show an error and recover through explicit refresh");
    let release;
    const barrier = new Promise((resolve) => (release = resolve));
    await p.route("**/iot-simulation?*", async (route) => {
      await barrier;
      await route.continue();
    });
    await p.locator("[data-iot-load]").click();
    await p.locator('[data-tab="home"]:visible').first().click();
    release();
    await p.waitForTimeout(250);
    assert.equal(await p.locator(".iot-panel").count(), 0);
    steps.push("A delayed simulator response cannot overwrite another page");
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      path.join(out, "report.json"),
      JSON.stringify({ at: new Date().toISOString(), steps, errors }, null, 2),
    );
    console.log(JSON.stringify({ passed: steps.length, steps, errors }, null, 2));
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
