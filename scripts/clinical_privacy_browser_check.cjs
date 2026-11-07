const { chromium } = require("playwright"),
  fs = require("fs"),
  path = require("path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, ".."),
  out = path.join(root, "test-results", "clinical-privacy"),
  base = process.env.NEUROTWIN_BASE_URL || "http://127.0.0.1:8141";
const password = fs
  .readFileSync(path.join(root, ".env"), "utf8")
  .split(/\r?\n/)
  .find((s) => s.startsWith("DEMO_PASSWORD="))
  .slice(14);
fs.mkdirSync(out, { recursive: true });
const wait = async (p, fn) => {
  for (let i = 0; i < 200; i++) {
    if (await p.evaluate(fn)) return;
    await p.waitForTimeout(100);
  }
  throw Error("Clinical/privacy condition timed out");
};
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
      acceptDownloads: true,
      viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 },
    });
    const p = await ctx.newPage();
    p.on("pageerror", (e) => errors.push(e.message));
    await p.goto(base + (mobile ? "/mobile/" : "/dashboard/"));
    if (mobile) await p.locator("[name=username]").selectOption(role);
    else await p.locator("[name=username]").fill(role);
    await p.locator("[name=password]").fill(password);
    await p.locator("#login button").click();
    await p.locator(mobile ? ".scope" : ".topbar").waitFor();
    return p;
  };
  try {
    const patient = await open("participant", true),
      doctor = await open("clinician", false);
    await doctor.locator('.sidebar [data-tab="patient"]').click();
    await doctor.locator(".clinical-plan-history").waitFor();
    const title = "Synthetic review plan " + Date.now();
    await doctor.locator("#plan [name=title]").fill(title);
    await doctor
      .locator("#plan [name=instructions]")
      .fill("Ask your chosen contact to help prepare your appointment.");
    await doctor.locator("#plan button").click();
    await doctor
      .getByText("Draft saved. It is not active until reviewed and approved.", { exact: true })
      .waitFor();
    const draft = await doctor.evaluate(
      (title) => S.data.records.find((r) => r.kind === "plan" && r.payload.title === title),
      title,
    );
    assert.equal(draft.status, "draft");
    await patient.reload();
    await patient.locator(".scope").waitFor();
    assert.equal(
      await patient.evaluate(
        (title) => S.data.records.some((r) => r.payload.title === title),
        title,
      ),
      false,
    );
    steps.push("Draft plan is persisted and remains hidden from patient");
    doctor.once("dialog", (d) => d.dismiss());
    await doctor.locator(`[data-approve="${draft.id}"]`).click();
    assert.equal(
      await doctor.evaluate((id) => S.data.records.find((r) => r.id === id).status, draft.id),
      "draft",
    );
    doctor.once("dialog", (d) => d.accept());
    await doctor.locator(`[data-approve="${draft.id}"]`).click();
    await doctor
      .getByText(
        "Approved revision saved. Mobile can refresh the current plan. No EHR dispatch occurred.",
        { exact: true },
      )
      .waitFor();
    const signed = await doctor.evaluate((id) => S.data.records.find((r) => r.id === id), draft.id);
    assert.equal(signed.status, "approved");
    assert.equal(signed.payload.signed_by, "clinician");
    assert.equal(signed.payload.content_hash.length, 64);
    await patient.reload();
    await patient.locator(".scope").waitFor();
    assert.equal(
      await patient.evaluate((id) => S.data.records.find((r) => r.id === id)?.status, draft.id),
      "approved",
    );
    steps.push("Approval requires confirmation and exposes authenticated revision to patient");
    for (const width of [1440, 1024, 768]) {
      await doctor.setViewportSize({ width, height: 1000 });
      assert.equal(
        await doctor.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
        false,
      );
      await doctor.screenshot({ path: path.join(out, `patient-${width}.png`), fullPage: true });
    }
    steps.push("Patient plan history, provenance and authoring form fit desktop and tablet widths");
    await patient.locator('[data-tab="settings"]:visible').first().click();
    await patient.locator("#memorySettings [name=enabled]").check();
    await patient
      .locator("#memorySettings [name=preferred_name]")
      .fill("Synthetic private preference");
    await patient.locator("#memorySettings button").click();
    await patient.getByText("Your memory choices were saved.", { exact: true }).waitFor();
    let exports = 0;
    patient.on("request", (r) => {
      if (r.url().endsWith("/memory/export")) exports++;
    });
    patient.once("dialog", (d) => d.dismiss());
    await patient.locator("#exportMemory").click();
    assert.equal(exports, 0);
    const download = patient.waitForEvent("download");
    patient.once("dialog", (d) => d.accept());
    await patient.locator("#exportMemory").click();
    const file = await download;
    const data = JSON.parse(fs.readFileSync(await file.path(), "utf8"));
    assert.equal(data.memory.preferred_name, "Synthetic private preference");
    assert.equal(data.patient_id, "patient-demo");
    assert.equal(data.schema_version, "neurotwin.companion-memory.v1");
    assert.equal(exports, 1);
    steps.push(
      "Private memory export requires explicit confirmation and downloads actual participant-scoped JSON",
    );
    await patient.locator("#forgetMemory").click();
    await patient
      .getByText("Conversation memory and preferences were cleared.", { exact: true })
      .waitFor();
    assert.equal(await patient.locator("#memorySettings [name=preferred_name]").inputValue(), "");
    assert.equal(data.memory.preferred_name, "Synthetic private preference");
    steps.push("Forget clears server memory; prior download is explicitly outside app deletion");
    await patient.screenshot({ path: path.join(out, "memory-390.png"), fullPage: true });
    const family = await open("family", true);
    assert.equal(await family.locator("[data-revoke-access]").count(), 0);
    patient.once("dialog", (d) => d.dismiss());
    await patient.locator('[data-revoke-access="family"]').click();
    assert.equal(await patient.locator('[data-revoke-access="family"]').count(), 1);
    patient.once("dialog", (d) => d.accept());
    await patient.locator('[data-revoke-access="family"]').click();
    await patient
      .getByText("Access removed. Previously downloaded information is not recalled.", {
        exact: true,
      })
      .waitFor();
    await family.evaluate(() => refresh());
    await family
      .getByRole("heading", { name: "No active patient workspace", exact: true })
      .waitFor();
    assert.equal(await family.evaluate(() => S.data), null);
    assert.equal(await family.evaluate(() => S.care.inbox), null);
    steps.push(
      "Participant access removal requires confirmation; revoked family refresh clears cached patient and messaging context",
    );
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      path.join(out, "report.json"),
      JSON.stringify(
        {
          status: "passed",
          steps,
          errors,
          at: new Date().toISOString(),
          data: "synthetic; no live AI",
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
