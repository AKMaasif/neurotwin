const { chromium } = require("playwright");
const fs = require("fs"),
  path = require("path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, ".."),
  out = path.join(root, "test-results", "password-change");
const base = process.env.NEUROTWIN_BASE_URL || "http://127.0.0.1:8140";
const password = fs
  .readFileSync(path.join(root, ".env"), "utf8")
  .split(/\r?\n/)
  .find((s) => s.startsWith("DEMO_PASSWORD="))
  .slice(14);
const replacement = "Synthetic browser replacement passphrase 2026";
fs.mkdirSync(out, { recursive: true });
(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH }
      : {}),
  });
  const errors = [],
    steps = [];
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
    p.on("pageerror", (e) => errors.push(e.stack || e.message));
    await p.goto(base + (desktop ? "/dashboard/" : "/mobile/"));
    await p.locator(desktop ? ".topbar" : ".scope").waitFor();
    await p
      .locator(`[data-tab="${desktop ? "account" : "settings"}"]:visible`)
      .first()
      .click();
    await p.locator(".account-sessions > summary").click();
    return { ctx, p };
  };
  const fill = async (p, current, next, confirmation = next) => {
    await p.locator('[name="current_password"]').fill(current);
    await p.locator('[name="new_password"]').fill(next);
    await p.locator('[name="confirm_password"]').fill(confirmation);
  };
  const submit = (p) =>
    p.getByRole("button", { name: "Change password and sign out", exact: true }).click();
  try {
    const a = await open("participant"),
      b = await open("participant"),
      family = await open("family");
    let requests = 0;
    a.p.on("request", (r) => {
      if (r.url().endsWith("/account/password")) requests++;
    });
    await fill(a.p, password, replacement, replacement + " mismatch");
    await submit(a.p);
    await a.p.locator("[data-account-state]").filter({ hasText: "do not match" }).waitFor();
    assert.equal(requests, 0);
    await fill(a.p, password, replacement);
    a.p.once("dialog", (d) => d.dismiss());
    await submit(a.p);
    assert.equal(requests, 0);
    assert.equal((await a.ctx.request.get(base + "/api/session")).status(), 200);
    steps.push("Mismatch and cancelled confirmation send no credential-change request");
    await fill(a.p, "incorrect-current-password", replacement);
    a.p.once("dialog", (d) => d.accept());
    await submit(a.p);
    await a.p
      .locator("[data-account-state]")
      .filter({ hasText: "Current password is incorrect" })
      .waitFor();
    assert.equal(await a.p.locator('[name="current_password"]').inputValue(), "");
    assert.equal(await a.p.locator('[name="new_password"]').inputValue(), "");
    assert.equal((await a.ctx.request.get(base + "/api/session")).status(), 200);
    steps.push(
      "Wrong current password preserves access, shows a safe error and clears credential fields",
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
    steps.push("Password controls reflow at phone/tablet/desktop widths and enlarged text");
    await fill(a.p, password, replacement);
    a.p.once("dialog", (d) => d.accept());
    await submit(a.p);
    await a.p.locator("#login").waitFor();
    assert.equal(await a.p.locator('[name="password"]').inputValue(), "");
    assert.equal((await b.ctx.request.get(base + "/api/session")).status(), 401);
    assert.equal((await family.ctx.request.get(base + "/api/session")).status(), 200);
    await b.p.locator("#login").waitFor();
    assert.equal(
      (
        await b.ctx.request.post(base + "/api/login", {
          data: { username: "participant", password },
        })
      ).status(),
      401,
    );
    await a.p.locator('[name="password"]').fill(replacement);
    await a.p.getByRole("button", { name: "Sign in", exact: true }).click();
    await a.p.locator(".scope").waitFor();
    assert.equal(await a.p.evaluate(() => S.user.id), "participant");
    steps.push(
      "Successful change signs out all own sessions, preserves other users and accepts only the new password",
    );
    const clinician = await open("clinician", true);
    await clinician.p.screenshot({ path: path.join(out, "clinical.png"), fullPage: true });
    await fill(clinician.p, password, replacement);
    clinician.p.once("dialog", (d) => d.accept());
    await submit(clinician.p);
    await clinician.p.locator("#login").waitFor();
    await clinician.p.locator('[name="password"]').fill(replacement);
    await clinician.p.getByRole("button", { name: "Sign in", exact: true }).click();
    await clinician.p.locator(".topbar").waitFor();
    steps.push("Clinical Account security uses the same verified change-and-sign-in flow");
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      path.join(out, "report.json"),
      JSON.stringify(
        {
          at: new Date().toISOString(),
          mode: "fresh isolated synthetic accounts only; no live account credentials changed",
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
