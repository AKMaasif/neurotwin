const { chromium } = require("playwright");
const fs = require("fs"),
  path = require("path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, ".."),
  out = path.join(root, "test-results");
const base = process.env.NEUROTWIN_BASE_URL || "http://127.0.0.1:8140";
const password = fs
  .readFileSync(path.join(root, ".env"), "utf8")
  .split(/\r?\n/)
  .find((s) => s.startsWith("DEMO_PASSWORD="))
  .slice(14);
const tag = String(Date.now()),
  fixture = (ext) => path.join(out, "chat-fixtures", "synthetic." + ext);
const wait = async (page, fn, arg) => {
  const end = Date.now() + 45000;
  while (Date.now() < end) {
    if (await page.evaluate(fn, arg)) return;
    await page.waitForTimeout(150);
  }
  throw Error("Multimedia condition timed out: " + String(fn));
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
  let patient;
  const open = async (role, mobile) => {
    const ctx = await browser.newContext({
      viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 },
      permissions: ["microphone"],
    });
    const page = await ctx.newPage();
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(base + (mobile ? "/mobile/" : "/dashboard/"));
    if (mobile) await page.locator("[name=username]").selectOption(role);
    else await page.locator("[name=username]").fill(role);
    await page.locator("[name=password]").fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page
      .getByRole("button", { name: mobile ? "Messages" : "Care messages", exact: true })
      .first()
      .click();
    await page.locator("#care-refresh").waitFor();
    return page;
  };
  const choose = async (page, peer) => {
    if (await page.locator("#care-back").isVisible()) await page.locator("#care-back").click();
    await page.locator(`[data-care-contact="${peer}"]`).click();
    await wait(page, () => !!S.care.thread && !S.care.busy);
  };
  const select = async (page, files) => {
    await page.locator("#care-attach").click();
    await page.locator("#care-file-picker").setInputFiles(files);
    await wait(page, () => !!S.care.batch?.files.length);
  };
  const send = async (page, caption) => {
    await page.locator("#care-compose textarea").fill(caption);
    await page.locator("#care-send").click();
    await wait(
      page,
      (text) => !S.care.batch && S.care.thread.messages.some((m) => m.body === text),
      caption,
    );
    return page.evaluate((text) => S.care.thread.messages.find((m) => m.body === text), caption);
  };
  try {
    patient = await open("participant", true);
    const family = await open("family", true),
      doctor = await open("clinician", false);
    await choose(patient, "family");
    await choose(family, "participant");
    let uploads = 0;
    patient.on("request", (r) => {
      if (r.method() === "POST" && /\/uploads$/.test(r.url())) uploads++;
    });
    await select(patient, [fixture("jpg"), fixture("png")]);
    assert.equal(uploads, 0);
    await patient.locator("[data-remove-file='1']").click();
    assert.equal(await patient.evaluate(() => S.care.batch.files.length), 1);
    await patient.locator("#care-cancel-files").click();
    assert.equal(uploads, 0);
    steps.push("local attachment preview, individual removal and cancellation create no upload");

    let latest;
    for (const [index, exts] of [
      ["jpg", "png", "webp", "mp4"],
      ["webm", "wav", "mp3", "m4a"],
      ["ogg", "txt", "csv", "docx", "xlsx"],
    ].entries()) {
      await select(patient, exts.map(fixture));
      latest = await send(patient, `Synthetic multimedia ${tag} batch ${index}`);
      assert.equal(latest.attachments.length, exts.length);
      await wait(family, (id) => S.care.thread.messages.some((m) => m.id === id), latest.id);
      assert.equal(
        await family.evaluate(
          (id) => S.care.thread.messages.find((m) => m.id === id).attachments.length,
          latest.id,
        ),
        exts.length,
      );
    }
    steps.push(
      "thirteen actual image/video/audio/Office/text types commit and reach the family through authenticated realtime",
    );
    await patient.locator("#care-latest").click();
    await wait(patient, () => !S.care.busy);
    await wait(
      patient,
      (id) => !!S.care.thread.messages.find((m) => m.id === id)?.receipt.delivered_at,
      latest.id,
    );
    assert.equal(latest.opened_at, null);
    steps.push("delivery is recipient synchronization, distinct from explicit opening");

    await family.locator(".chat-open-image").first().click();
    await family.locator("dialog.chat-viewer img").waitFor();
    assert.equal(
      await family
        .locator("dialog.chat-viewer img")
        .evaluate((img) => img.complete && img.naturalWidth > 0),
      true,
    );
    await family.locator("dialog.chat-viewer button").click();
    const audio = family.locator(".chat-audio").last();
    await audio.locator("audio").evaluate((a) => {
      a.muted = true;
    });
    await audio.locator(".audio-play").click();
    await wait(family, () =>
      [...document.querySelectorAll(".chat-audio audio")].some((a) => a.currentTime > 0),
    );
    await audio.locator(".audio-speed").selectOption("1.5");
    assert.equal(await audio.locator("audio").evaluate((a) => a.playbackRate), 1.5);
    await wait(family, () =>
      [...document.querySelectorAll(".chat-audio audio")].some((a) => a.ended),
    );
    assert.notEqual(await audio.locator(".audio-total").textContent(), "0:00");
    steps.push(
      "private image viewer and measured custom audio controls decode real media without autoplay",
    );

    await choose(doctor, "participant");
    await select(doctor, [fixture("pdf")]);
    const pdf = await send(doctor, `Synthetic clinician PDF ${tag}`);
    await choose(patient, "clinician");
    await wait(patient, (id) => S.care.thread.messages.some((m) => m.id === id), pdf.id);
    const denied = await family.evaluate(
      async (url) => (await fetch(url)).status,
      pdf.attachments[0].url,
    );
    assert.equal(denied, 404);
    await patient.locator(".chat-open-image").last().click();
    await wait(patient, () => document.querySelector("dialog img")?.naturalWidth > 0);
    await patient.locator("dialog button").click();
    steps.push(
      "clinician PDF reaches patient with reconstructed preview and denies unrelated family retrieval",
    );

    await patient.locator(`[data-reply="${pdf.id}"]`).evaluate((b) => b.click());
    await patient.locator("#care-compose textarea").fill(`Synthetic reply ${tag}`);
    await patient.locator("#care-send").click();
    await wait(patient, () => !S.care.busy && !S.care.pending.clinician);
    assert.equal(await patient.locator(".chat-quote").last().textContent(), "Reply" + pdf.body);
    await patient.locator("#care-search [name=q]").fill(`Synthetic reply ${tag}`);
    await patient.locator("#care-search button").first().click();
    await wait(patient, () => S.care.thread.messages.length === 1);
    const replyId = await patient.evaluate(() => S.care.thread.messages[0].id);
    patient.once("dialog", (d) => d.accept());
    await patient.locator(`[data-withdraw="${replyId}"]`).evaluate((b) => b.click());
    await wait(patient, () => !S.care.thread.messages.length);
    await patient.locator("#care-latest").click();
    await wait(patient, () => !S.care.busy);
    assert(
      await patient.evaluate(
        (id) => !!S.care.thread.messages.find((m) => m.id === id)?.withdrawn_at,
        replyId,
      ),
    );
    steps.push(
      "quoted reply, literal search and author withdrawal preserve the canonical timeline",
    );

    await choose(patient, "family");
    const large = {
      name: "synthetic-resume.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Synthetic resumable line\n".repeat(100000)),
    };
    const offsets = [];
    await patient.route("**/messages/uploads/*", async (route) => {
      const req = route.request();
      if (req.method() !== "PATCH") return route.continue();
      const offset = Number(req.headers()["upload-offset"]);
      offsets.push(offset);
      if (offset > 0) return route.abort("failed");
      return route.continue();
    });
    await select(patient, [large]);
    await patient.locator("#care-send").click();
    await wait(patient, () => S.care.batch?.phase === "failed");
    const uploadId = await patient.evaluate(() => S.care.batch.files[0].upload_id);
    const commandId = await patient.evaluate(() => S.care.batch.command_id);
    assert(offsets.includes(1048576));
    await patient.unroute("**/messages/uploads/*");
    await patient.reload();
    await patient.getByRole("button", { name: "Messages", exact: true }).first().click();
    await patient.locator("#care-refresh").waitFor();
    await choose(patient, "family");
    await wait(patient, (id) => S.care.recoverable?.some((r) => r.id === id), uploadId);
    await patient.locator(`[data-recover-command="${commandId}"]`).evaluate((b) => b.click());
    await patient.locator("#care-file-picker").setInputFiles(large);
    await wait(patient, () => !!S.care.batch?.files.length);
    assert.equal(await patient.evaluate(() => S.care.batch.files[0].offset), 1048576);
    const resumed = await send(patient, `Synthetic recovered ${tag}`);
    assert.equal(resumed.command_id, commandId);
    steps.push(
      "interrupted multi-chunk upload survives refresh and resumes the same IDs at the confirmed offset",
    );

    await patient.evaluate(() => {
      const c = S.care,
        n = c.lastEvent;
      for (const seq of [n, n - 1, n])
        c.source.dispatchEvent(
          new MessageEvent("care", {
            data: JSON.stringify({ sequence: seq, type: "message.created" }),
          }),
        );
    });
    const ids = await patient.evaluate(() => S.care.thread.messages.map((m) => m.id));
    assert.equal(new Set(ids).size, ids.length);
    steps.push("duplicate and out-of-order realtime events do not duplicate canonical messages");

    await family.locator("#care-voice-record").click();
    await wait(family, () => S.care.voice?.phase === "recording");
    await family.waitForTimeout(650);
    await family.locator("#care-record-pause").click();
    assert.equal(await family.evaluate(() => S.care.voice.rec.state), "paused");
    await family.waitForTimeout(300);
    await family.locator("#care-record-pause").click();
    await family.waitForTimeout(650);
    await family.locator("#care-voice-finish").click();
    await wait(family, () => S.care.voice?.phase === "preview");
    assert.equal(
      await family.evaluate(() =>
        S.care.voice.stream.getTracks().every((t) => t.readyState === "ended"),
      ),
      true,
    );
    assert(await family.evaluate(() => S.care.voice.blob.size > 24000));
    await family.locator("#care-voice-form textarea").fill(`Synthetic paused recording ${tag}`);
    await family.locator("#care-voice-form button.primary").click();
    await wait(family, () => !S.care.voice);
    await wait(
      patient,
      (text) => S.care.thread.messages.some((m) => m.body === text),
      `Synthetic paused recording ${tag}`,
    );
    steps.push(
      "MediaRecorder pause/resume retains audible segments, releases microphone and explicitly sends family voice to patient",
    );
    for (const page of [patient, doctor]) {
      assert.equal(
        await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),
        false,
      );
      await page.screenshot({
        path: path.join(
          out,
          page === patient ? "multimedia-mobile.png" : "multimedia-dashboard.png",
        ),
        fullPage: true,
      });
    }
    steps.push("desktop and mobile viewport layouts have no horizontal overflow");
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      path.join(out, "multimedia-browser-check.json"),
      JSON.stringify({ status: "passed", steps, errors, at: new Date().toISOString() }, null, 2),
    );
    console.log(JSON.stringify({ status: "passed", steps, errors }));
  } catch (error) {
    if (patient)
      console.error(
        "Synthetic messaging state:",
        await patient.evaluate(() => ({
          tab: S.tab,
          peer: S.care?.peer,
          error: S.care?.error,
          batch: S.care?.batch && {
            phase: S.care.batch.phase,
            error: S.care.batch.error,
            caption: S.care.batch.caption,
          },
          messages: S.care?.thread?.messages.map((message) => ({
            body: message.body,
            id: message.id,
          })),
        })),
      );
    if (patient)
      await patient.screenshot({ path: path.join(out, "multimedia-failure.png"), fullPage: true });
    console.error("Completed checks:", steps);
    throw error;
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e.stack);
  process.exitCode = 1;
});
