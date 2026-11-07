const { chromium } = require("playwright");
const fs = require("fs"),
  path = require("path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, ".."),
  out = path.join(root, "test-results", "workspaces");
const base = process.env.NEUROTWIN_BASE_URL || "http://127.0.0.1:8142";
const password = fs
  .readFileSync(path.join(root, ".env"), "utf8")
  .split(/\r?\n/)
  .find((x) => x.startsWith("DEMO_PASSWORD="))
  .slice(14);
fs.mkdirSync(out, { recursive: true });
const wait = async (p, fn) => {
  for (let n = 0; n < 200; n++) {
    if (await p.evaluate(fn)) return;
    await p.waitForTimeout(100);
  }
  throw Error("Workspace condition timed out");
};
(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH }
      : {}),
    args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
  });
  const errors = [],
    steps = [];
  const record = steps.push.bind(steps);
  steps.push = (...items) => {
    console.log(items.join("\n"));
    return record(...items);
  };
  const open = async (role, desktop = false) => {
    const ctx = await browser.newContext({
      viewport: desktop ? { width: 1440, height: 1000 } : { width: 390, height: 844 },
      permissions: ["microphone"],
    });
    const response = await ctx.request.post(base + "/api/login", {
      data: { username: role, password },
    });
    assert.equal(response.status(), 200);
    const identity = await response.json();
    const p = await ctx.newPage();
    p.on("pageerror", (e) => errors.push(e.message));
    await p.goto(base + (desktop ? "/dashboard/" : "/mobile/"));
    await wait(p, () => !!document.querySelector(".scope,.topbar,.workspace-state"));
    return { p, ctx, identity };
  };
  const choose = async (p, id) => {
    await p.locator("#active-workspace").selectOption(id);
    await p.waitForFunction((id) => S.pid === id && !!S.data && !S.workspaceChanging, id);
    assert.equal(await p.evaluate(() => S.pid), id);
  };
  const inbox = async (p, peer) => {
    await p.locator('[data-tab="messages"]').first().click();
    await p.locator(`[data-care-contact="${peer}"]`).click();
    await p.locator("#care-compose textarea").waitFor();
  };
  try {
    const a = await open("participant"),
      b = await open("other");
    for (const [actor, pid, label] of [
      [a, "patient-demo", "Only patient A"],
      [b, "patient-other", "Only patient B"],
    ]) {
      const r = await actor.ctx.request.post(
        `${base}/api/patients/${pid}/messages/threads/family`,
        {
          headers: { "X-CSRF-Token": actor.identity.csrf },
          data: { command_id: "workspace_" + crypto.randomUUID(), body: label },
        },
      );
      assert.equal(r.status(), 200);
    }
    const { p: family } = await open("family");
    assert.equal(await family.evaluate(() => S.pid), null);
    assert.equal(await family.locator("#active-workspace option").count(), 3);
    steps.push(
      "Multiple grants require an explicit choice; participant with one grant opens only their patient",
    );
    await choose(family, "patient-demo");
    await inbox(family, "participant");
    await family.locator(".care-body").filter({ hasText: "Only patient A" }).first().waitFor();
    await family.locator("#care-compose textarea").fill("Private unsent A draft");
    family.once("dialog", (d) => d.dismiss());
    await family.locator("#active-workspace").selectOption("patient-other");
    await family.waitForTimeout(300);
    assert.equal(await family.evaluate(() => S.pid), "patient-demo");
    assert.equal(
      await family.locator("#care-compose textarea").inputValue(),
      "Private unsent A draft",
    );
    await family.evaluate(() => {
      window.oldFeed = S.care.source;
    });
    family.once("dialog", (d) => d.accept());
    await choose(family, "patient-other");
    assert.equal(await family.evaluate(() => oldFeed.readyState), 2);
    await inbox(family, "other");
    await family.locator(".care-body").filter({ hasText: "Only patient B" }).first().waitFor();
    assert.equal(await family.getByText("Only patient A", { exact: true }).count(), 0);
    assert.equal(await family.locator("#care-compose textarea").inputValue(), "");
    steps.push(
      "Cancelled switch preserves draft; confirmed switch closes SSE and clears patient A messages and drafts",
    );
    await family.locator("#care-voice-record").click();
    await wait(family, () => S.care.voice?.phase === "recording");
    await family.evaluate(() => {
      window.oldStream = S.care.voice.stream;
    });
    family.once("dialog", (d) => d.accept());
    await choose(family, "patient-demo");
    assert(
      await family.evaluate(() => oldStream.getTracks().every((t) => t.readyState === "ended")),
    );
    steps.push(
      "Switching stops real MediaRecorder fake-device tracks and disposes the unsent recording",
    );
    let release, held;
    const gate = new Promise((r) => (release = r)),
      started = new Promise((r) => (held = r));
    await family.route("**/workspace?delayed=1", async (route) => {
      const response = await route.fetch();
      held();
      await gate;
      await route.fulfill({ response });
    });
    await family.evaluate(() => {
      window.late = api(`/patients/${S.pid}/workspace?delayed=1`)
        .then((d) => {
          S.data = d;
          return "accepted";
        })
        .catch((e) => e.message);
    });
    await Promise.race([
      started,
      new Promise((_, reject) =>
        setTimeout(() => reject(Error("Delayed route not reached")), 10000),
      ),
    ]);
    await choose(family, "patient-other");
    release();
    assert.match(await family.evaluate(() => window.late), /Workspace changed/);
    assert.equal(await family.evaluate(() => S.data.patient.id), "patient-other");
    steps.push("Actual delayed server response is rejected after a workspace change");
    await family.locator('[data-tab="settings"]:visible').first().click();
    await family.locator("#size").click();
    assert(await family.evaluate(() => S.accountTextLarge));
    await choose(family, "patient-demo");
    assert(await family.evaluate(() => document.documentElement.classList.contains("large")));
    steps.push("Family readability is local and persists across patient switching");
    const { p: doctor } = await open("clinician", true);
    await choose(doctor, "patient-readonly");
    assert.equal(
      await doctor
        .locator(
          '.sidebar [data-tab="sources"],.sidebar [data-tab="queue"],.sidebar [data-tab="report"]',
        )
        .count(),
      0,
    );
    assert.equal(await doctor.evaluate(() => S.documents.length), 0);
    await doctor
      .getByText("Clinical source access is not granted for this workspace.", { exact: true })
      .waitFor();
    assert.equal(
      await doctor.evaluate(async () => {
        try {
          await activateWorkspace("not-authorized");
          return false;
        } catch {
          return S.pid === "patient-readonly";
        }
      }),
      true,
    );
    steps.push(
      "Summary-only clinician loads without clinical documents, editing or report access; forged choice rejected",
    );
    const revoke = await b.ctx.request.post(
      `${base}/api/patients/patient-other/grants/family/revoke`,
      { headers: { "X-CSRF-Token": b.identity.csrf } },
    );
    assert.equal(revoke.status(), 200);
    await family.locator("#active-workspace").selectOption("patient-other");
    await family.waitForTimeout(400);
    assert.equal(await family.evaluate(() => S.pid), "patient-demo");
    assert.equal(await family.locator("#active-workspace").count(), 0);
    steps.push(
      "Revocation is checked again before activation and removes the stale directory option",
    );
    const revokeA = await a.ctx.request.post(
      `${base}/api/patients/patient-demo/grants/family/revoke`,
      { headers: { "X-CSRF-Token": a.identity.csrf } },
    );
    assert.equal(revokeA.status(), 200);
    const { p: empty } = await open("family");
    await empty
      .getByRole("heading", { name: "No active patient workspace", exact: true })
      .waitFor();
    await empty.locator("#workspace-signout").click();
    await empty.locator("#login").waitFor();
    steps.push("No-grant account gets an honest empty state and working sign out");
    await doctor.screenshot({ path: path.join(out, "summary-only-1440.png"), fullPage: true });
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      path.join(out, "browser-check.json"),
      JSON.stringify(
        {
          status: "passed",
          steps,
          errors,
          at: new Date().toISOString(),
          data: "isolated synthetic; fake microphone; no paid AI calls",
        },
        null,
        2,
      ),
    );
    console.log(JSON.stringify({ status: "passed", steps }));
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e.stack);
  process.exitCode = 1;
});
