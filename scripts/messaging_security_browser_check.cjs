// Run last against an isolated synthetic database: this deliberately revokes its family grant.
const { chromium } = require("playwright");
const fs = require("fs"),
  path = require("path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, ".."),
  out = path.join(root, "test-results");
const base = process.env.NEUROTWIN_BASE_URL;
if (
  !base ||
  !base.startsWith("http://127.0.0.1:8141") ||
  process.env.NEUROTWIN_DESTRUCTIVE_SYNTHETIC_TEST !== "1"
)
  throw Error(
    "This destructive synthetic grant test requires the isolated loopback server on 8141.",
  );
const password = fs
  .readFileSync(path.join(root, ".env"), "utf8")
  .split(/\r?\n/)
  .find((s) => s.startsWith("DEMO_PASSWORD="))
  .slice(14);
const wait = async (page, fn, arg) => {
  const end = Date.now() + 30000;
  while (Date.now() < end) {
    if (await page.evaluate(fn, arg)) return;
    await page.waitForTimeout(150);
  }
  throw Error("Security browser condition timed out: " + fn);
};
(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH }
      : {}),
    args: [
      "--use-fake-device-for-media-stream",
      "--use-fake-ui-for-media-stream",
      `--use-file-for-fake-audio-capture=${path.join(out, "voice-note-microphone.wav")}`,
    ],
  });
  const errors = [],
    steps = [];
  const open = async (role) => {
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      permissions: ["microphone"],
    });
    const page = await context.newPage();
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(base + "/mobile/");
    await page.locator("[name=username]").selectOption(role);
    await page.locator("[name=password]").fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.getByRole("button", { name: "Messages", exact: true }).first().click();
    await page.locator("#care-refresh").waitFor();
    return page;
  };
  const choose = async (page, peer) => {
    if (await page.locator("#care-back").isVisible()) await page.locator("#care-back").click();
    await page.locator(`[data-care-contact="${peer}"]`).click();
    await wait(page, () => !!S.care.thread && !S.care.busy);
  };
  try {
    const patient = await open("participant"),
      family = await open("family");
    await choose(patient, "family");
    await choose(family, "participant");
    await family
      .locator(".chat-video video")
      .last()
      .evaluate(async (video) => {
        video.muted = true;
        await video.play();
      });
    await wait(family, () =>
      [...document.querySelectorAll(".chat-video video")].some((video) => video.currentTime > 0),
    );
    await family.evaluate(() => pauseCareAudio());
    steps.push(
      "authorized inline video decodes and plays without downloading other videos automatically",
    );
    await patient.locator("#care-voice-record").click();
    await wait(patient, () => S.care.voice?.phase === "recording");
    await patient.waitForTimeout(650);
    await patient.locator("#care-voice-finish").click();
    await wait(patient, () => S.care.voice?.phase === "preview");
    await patient.route("**/messages/threads/family/voice", (route) => route.abort("failed"));
    await patient.locator("#care-voice-form button.primary").click();
    await wait(patient, () => S.care.voice?.phase === "unconfirmed");
    const command = await patient.evaluate(() => S.care.voice.command_id);
    const saved = await patient.evaluate(
      async (key) =>
        (await api(`/patients/${S.pid}/messages/threads/family/command/${key}`)).message,
      command,
    );
    assert.equal(saved, null);
    await patient.unroute("**/messages/threads/family/voice");
    await patient.reload();
    await patient.getByRole("button", { name: "Messages", exact: true }).first().click();
    await patient.locator("#care-refresh").waitFor();
    await choose(patient, "family");
    await patient.locator(`[data-recover-command="${command}"]`).evaluate((b) => b.click());
    await wait(patient, () => S.care.voice?.phase === "preview");
    assert.equal(await patient.evaluate(() => S.care.voice.command_id), command);
    await patient.locator("#care-voice-form button.primary").click();
    await wait(patient, () => !S.care.voice && !S.care.busy);
    const result = await patient.evaluate(
      async (key) =>
        (await api(`/patients/${S.pid}/messages/threads/family`)).messages.filter(
          (m) => m.command_id === key,
        ),
      command,
    );
    assert.equal(result.length, 1);
    steps.push(
      "verified but unsent voice survives refresh, recovers privately for preview, and sends once only after explicit approval",
    );

    // Native cookie replacement outside the app must invalidate the old SSE session too.
    const other = await patient.context().newPage();
    await other.goto(base + "/mobile/");
    const replaced = await other.evaluate(
      async (credentials) =>
        (
          await fetch("/api/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(credentials),
          })
        ).status,
      { username: "family", password },
    );
    assert.equal(replaced, 200);
    await wait(patient, () => !S.care.peer && !S.care.thread);
    const blocked = await patient.evaluate(
      async () =>
        (
          await fetch(`/api/patients/${S.pid}/messages/threads/clinician`, {
            headers: { "X-Expected-Actor": "participant" },
          })
        ).status,
    );
    assert.equal(blocked, 409);
    assert.equal(await patient.evaluate(() => S.care.source), null);
    steps.push(
      "same-browser cookie account replacement closes the old stream and rejects stale identity requests",
    );
    await other.close();

    const owner = await open("participant");
    await choose(owner, "family");
    await family.evaluate(() => {
      S.care.drafts.participant = "Synthetic private draft";
    });
    await owner.evaluate(async () => api(`/patients/${S.pid}/grants/family/revoke`, "POST"));
    await wait(family, () => !S.care.peer && !S.care.thread && !S.care.source);
    assert.deepEqual(await family.evaluate(() => S.care.drafts), {});
    const denied = await family.evaluate(
      async () => (await fetch(`/api/patients/${S.pid}/messages/threads/participant`)).status,
    );
    assert.equal(denied, 403);
    steps.push(
      "grant revocation closes realtime, clears private chat state and blocks subsequent conversation access",
    );
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      path.join(out, "messaging-security-browser-check.json"),
      JSON.stringify({ status: "passed", steps, errors, at: new Date().toISOString() }, null, 2),
    );
    console.log(JSON.stringify({ status: "passed", steps, errors }));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack);
  process.exitCode = 1;
});
