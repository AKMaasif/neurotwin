const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const assert = require("node:assert/strict");
const base = process.env.NEUROTWIN_BASE_URL || "http://127.0.0.1:8140";
const root = path.resolve(__dirname, "..");
const out = path.join(root, "test-results");
const password = fs
  .readFileSync(path.join(root, ".env"), "utf8")
  .split(/\r?\n/)
  .find((s) => s.startsWith("DEMO_PASSWORD="))
  .slice(14);
const runId = Date.now().toString();
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
  let patient;
  const wait = async (page, fn) => {
    const until = Date.now() + 30000;
    while (Date.now() < until) {
      if (await page.evaluate(fn)) return;
      await page.waitForTimeout(150);
    }
    throw Error("Messaging condition timed out");
  };
  const login = async (page, role, mobile) => {
    if (mobile) await page.locator("[name=username]").selectOption(role);
    else await page.locator("[name=username]").fill(role);
    await page.locator("[name=password]").fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.locator(".scope").or(page.locator("#logout")).first().waitFor();
  };
  const open = async (role, mobile) => {
    const ctx = await browser.newContext({
      viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 },
    });
    const page = await ctx.newPage();
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(base + (mobile ? "/mobile/" : "/dashboard/"));
    await login(page, role, mobile);
    await page
      .getByRole("button", { name: mobile ? "Messages" : "Care messages", exact: true })
      .first()
      .click();
    await page.locator("#care-refresh").waitFor();
    return page;
  };
  const choose = async (page, id) => {
    if (await page.locator("#care-back").isVisible()) await page.locator("#care-back").click();
    await page.locator(`[data-care-contact="${id}"]`).click();
    await wait(page, () => !!S.care?.thread && !S.care.busy);
    await page.locator("#care-compose textarea").waitFor();
  };
  const send = async (page, text) => {
    await page.locator("#care-compose textarea").fill(text);
    await page.getByRole("button", { name: "Send message", exact: true }).click();
    await wait(
      page,
      () => !S.care.busy && !S.care.pending[S.care.peer] && !S.care.drafts[S.care.peer],
    );
    await page.locator(".care-body").filter({ hasText: text }).last().waitFor();
  };
  try {
    patient = await open("participant", true);
    const family = await open("family", true),
      doctor = await open("clinician", false);
    await choose(patient, "family");
    const text = `Synthetic transport request ${runId}`;
    await send(patient, text);
    assert.equal(await patient.evaluate(() => S.care.thread.messages.at(-1).state), "saved_in_app");
    await family.locator("#care-refresh").click();
    await wait(family, () => !S.care.busy);
    await choose(family, "participant");
    assert.equal(await family.evaluate(() => S.care.thread.messages.at(-1).opened_at), null);
    steps.push("patient-to-family message persists without an automatic opening receipt");
    await family.locator("#care-opened").click();
    await wait(
      family,
      () =>
        !S.care.busy &&
        S.care.thread.messages.every((m) => m.recipient_id !== S.user.id || m.opened_at),
    );
    await patient.locator("#care-latest").click();
    await wait(patient, () => !S.care.busy);
    assert.equal(
      await patient.evaluate(() => S.care.thread.messages.at(-1).state),
      "opened_in_app",
    );
    assert.equal(
      await patient.evaluate(() => {
        const h = document.querySelector(".care-history");
        return h.scrollHeight - h.clientHeight - h.scrollTop < 5;
      }),
      true,
    );
    steps.push("explicit recipient acknowledgement updates sender receipt");
    const literal = `<img src=x onerror="window.careXss=true"> Synthetic reply ${runId}`;
    await send(family, literal);
    await patient.locator("#care-latest").click();
    await wait(patient, () => !S.care.busy);
    await patient.getByText(literal, { exact: true }).waitFor();
    assert.equal(await patient.locator(".care-body img").count(), 0);
    assert.equal(await patient.evaluate(() => !!window.careXss), false);
    steps.push("family replies render as escaped plain text");
    await choose(doctor, "participant");
    assert.equal(await doctor.locator(".care-body").filter({ hasText: text }).count(), 0);
    await choose(family, "clinician");
    const clinicianText = `Synthetic appointment question ${runId}`;
    await send(family, clinicianText);
    await choose(doctor, "family");
    await doctor.getByText(clinicianText, { exact: true }).waitFor();
    await send(doctor, `Synthetic scheduling reply ${runId}`);
    steps.push(
      "family and clinician exchange direct messages while patient-family contents remain private",
    );
    // Commit the first request on the actual test server, then lose its response.
    await patient.evaluate(() => {
      carePolling = true;
    });
    let lost = false;
    await patient.route("**/messages/threads/family", async (route) => {
      if (route.request().method() === "POST" && !lost) {
        lost = true;
        const response = await route.fetch();
        assert.equal(response.status(), 200);
        await route.abort("failed");
      } else await route.continue();
    });
    const retryText = `Synthetic lost-response request ${runId}`;
    await patient.locator("#care-compose textarea").fill(retryText);
    await patient.getByRole("button", { name: "Send message", exact: true }).click();
    await patient.getByRole("button", { name: "Retry saving this message", exact: true }).waitFor();
    const key = await patient.evaluate(() => S.care.pending.family.command_id);
    await patient.getByRole("button", { name: "Retry saving this message", exact: true }).click();
    await wait(patient, () => !S.care.busy && !S.care.pending.family);
    const retryRows = await patient.evaluate(
      async (text) =>
        (await api(`/patients/${S.pid}/messages/threads/family`)).messages.filter(
          (m) => m.body === text,
        ),
      retryText,
    );
    assert.equal(retryRows.length, 1);
    assert.equal(retryRows[0].command_id, key);
    await patient.evaluate(() => {
      carePolling = false;
    });
    steps.push(
      "a committed message with a lost HTTP response retries under the same ID without duplication",
    );
    await patient.locator("#care-compose textarea").fill("Synthetic unsent draft");
    await patient.getByRole("button", { name: "Home", exact: true }).click();
    await patient.getByRole("button", { name: "Messages", exact: true }).first().click();
    await wait(patient, () => !!S.care.thread && !S.care.busy);
    assert.equal(
      await patient.locator("#care-compose textarea").inputValue(),
      "Synthetic unsent draft",
    );
    assert.equal(
      await patient.evaluate(() => document.documentElement.scrollWidth > innerWidth),
      false,
    );
    await patient.screenshot({ path: path.join(out, "messages-mobile.png"), fullPage: true });
    await doctor.screenshot({ path: path.join(out, "messages-dashboard.png"), fullPage: true });
    steps.push(
      "unsent draft survives in-session navigation and mobile layout has no horizontal overflow",
    );
    await patient.getByRole("button", { name: "Settings", exact: true }).click();
    const dismissed = new Promise((resolve) =>
      patient.once("dialog", async (d) => {
        await d.dismiss();
        resolve();
      }),
    );
    await patient.getByRole("button", { name: "Sign out", exact: true }).click();
    await dismissed;
    assert.equal(await patient.evaluate(() => S.user.id), "participant");
    const accepted = new Promise((resolve) =>
      patient.once("dialog", async (d) => {
        await d.accept();
        resolve();
      }),
    );
    await patient.getByRole("button", { name: "Sign out", exact: true }).click();
    await accepted;
    await patient.locator("#login").waitFor();
    await login(patient, "family", true);
    await patient.getByRole("button", { name: "Messages", exact: true }).first().click();
    await patient.locator("#care-refresh").waitFor();
    assert.deepEqual(await patient.evaluate(() => S.care.drafts), {});
    assert.deepEqual(await patient.evaluate(() => S.care.pending), {});
    steps.push(
      "sign-out warns before draft loss and clears message state before another account signs in",
    );
    await patient.getByRole("button", { name: "Companion", exact: true }).click();
    await patient.locator("#chatInput").fill("open messages");
    await patient.getByRole("button", { name: "Send", exact: true }).click();
    await patient.getByRole("heading", { name: "Care-circle messages", exact: true }).waitFor();
    await wait(patient, () => !!S.care.inbox);
    assert.equal(await patient.evaluate(() => S.care.peer), null);
    steps.push(
      "companion opens the inbox through the allowlist without sending or acknowledging messages",
    );
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      path.join(out, "message-browser-check.json"),
      JSON.stringify({ status: "passed", steps, errors, at: new Date().toISOString() }, null, 2),
    );
    console.log(JSON.stringify({ status: "passed", steps, errors }));
  } catch (e) {
    if (patient)
      await patient.screenshot({ path: path.join(out, "messages-failure.png"), fullPage: true });
    console.error("Completed checks:", steps);
    throw e;
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e.stack);
  process.exitCode = 1;
});
