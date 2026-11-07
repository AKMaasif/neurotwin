const { chromium } = require("playwright");
const fs = require("fs"),
  path = require("path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, ".."),
  out = path.join(root, "test-results", "account-sessions");
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
    return { ctx, p };
  };
  const load = async (p) => {
    const panel = p.locator(".account-sessions");
    if ((await panel.getAttribute("open")) === null) await panel.locator("summary").click();
    await panel.locator("[data-account-load]").click();
    await p.waitForFunction(
      () =>
        !document.querySelector(".account-sessions[aria-busy]") &&
        document
          .querySelector("[data-account-state]")
          ?.textContent.startsWith("Current session information"),
    );
  };
  try {
    const a = await open("participant"),
      b = await open("participant"),
      family = await open("family");
    await a.p.locator('[data-tab="settings"]:visible').first().click();
    await load(a.p);
    assert.match(await a.p.locator("[data-account-content]").innerText(), /1 other active session/);
    steps.push(
      "Mobile Settings reports the other session without pretending to identify its device",
    );
    a.p.once("dialog", (d) => d.dismiss());
    await a.p.locator("[data-account-revoke]").click();
    assert.equal((await b.ctx.request.get(base + "/api/session")).status(), 200);
    a.p.once("dialog", (d) => d.accept());
    await a.p.locator("[data-account-revoke]").click();
    await a.p
      .locator("[data-account-state]")
      .filter({ hasText: "1 other session signed out" })
      .waitFor();
    assert.equal((await a.ctx.request.get(base + "/api/session")).status(), 200);
    assert.equal((await b.ctx.request.get(base + "/api/session")).status(), 401);
    assert.equal((await family.ctx.request.get(base + "/api/session")).status(), 200);
    steps.push(
      "Cancellation preserves access; confirmed revocation keeps current and other-account sessions active",
    );
    await b.p.evaluate(async () => {
      try {
        await api("/account/sessions");
      } catch {}
    });
    await b.p.locator("#login").waitFor();
    assert.equal(await b.p.evaluate(() => S.user), null);
    assert.equal(await b.p.locator(".scope,.home-heading").count(), 0);
    steps.push(
      "A revoked client clears private views and returns to sign-in after its next authenticated request",
    );
    for (const width of [320, 390, 768, 1440]) {
      await a.p.setViewportSize({ width, height: 1000 });
      assert.equal(
        await a.p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
        false,
      );
    }
    await a.p.setViewportSize({ width: 320, height: 1000 });
    await a.p.evaluate(() => (document.documentElement.style.fontSize = "32px"));
    assert.equal(
      await a.p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
      false,
    );
    await a.p.screenshot({ path: path.join(out, "mobile-large.png"), fullPage: true });
    await a.p.evaluate(() => (document.documentElement.style.fontSize = ""));
    steps.push("Account controls reflow at phone/tablet/desktop widths and enlarged text");
    const clinician = await open("clinician", true),
      otherClinician = await open("clinician", true);
    await clinician.p.locator('[data-tab="account"]').click();
    await load(clinician.p);
    clinician.p.once("dialog", (d) => d.accept());
    await clinician.p.locator("[data-account-revoke]").click();
    await clinician.p
      .locator("[data-account-state]")
      .filter({ hasText: "1 other session signed out" })
      .waitFor();
    await otherClinician.p.evaluate(async () => {
      try {
        await api("/account/sessions");
      } catch {}
    });
    await otherClinician.p.locator("#login").waitFor();
    await clinician.p.screenshot({ path: path.join(out, "clinical.png"), fullPage: true });
    steps.push(
      "Clinical Account security provides the same scoped control and revoked-view cleanup",
    );
    await a.p.route("**/account/sessions", (route) =>
      route.fulfill({ status: 503, json: { detail: "Synthetic session service interruption" } }),
    );
    await a.p.locator("[data-account-load]").click();
    await a.p
      .locator("[data-account-state]")
      .filter({ hasText: "Synthetic session service interruption" })
      .waitFor();
    assert.equal(await a.p.locator("[data-account-content]").textContent(), "");
    await a.p.unroute("**/account/sessions");
    await load(a.p);
    steps.push(
      "An unavailable summary clears stale controls and recovers through explicit refresh",
    );
    await a.p.route("**/api/patients", (route) => route.fulfill({ json: [] }));
    await a.p.reload();
    await a.p.getByRole("heading", { name: "No active patient workspace", exact: true }).waitFor();
    await load(a.p);
    assert.equal(await a.p.locator("[data-account-content]").count(), 1);
    steps.push("Account security remains reachable without an active patient workspace");
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
