const { chromium } = require("playwright");
const fs = require("fs"),
  path = require("path"),
  assert = require("node:assert/strict");
const base = process.env.NEUROTWIN_BASE_URL || "http://127.0.0.1:8140";
const root = path.resolve(__dirname, ".."),
  out = path.join(root, "test-results");
fs.mkdirSync(out, { recursive: true });
const password = fs
  .readFileSync(path.join(root, ".env"), "utf8")
  .split(/\r?\n/)
  .find((s) => s.startsWith("DEMO_PASSWORD="))
  .slice(14);
const fixture = path.join(out, "voice-note-microphone.wav"),
  rate = 48000,
  frames = rate * 2;
const wav = Buffer.alloc(44 + frames * 2);
wav.write("RIFF", 0);
wav.writeUInt32LE(wav.length - 8, 4);
wav.write("WAVEfmt ", 8);
wav.writeUInt32LE(16, 16);
wav.writeUInt16LE(1, 20);
wav.writeUInt16LE(1, 22);
wav.writeUInt32LE(rate, 24);
wav.writeUInt32LE(rate * 2, 28);
wav.writeUInt16LE(2, 32);
wav.writeUInt16LE(16, 34);
wav.write("data", 36);
wav.writeUInt32LE(frames * 2, 40);
for (let i = 0; i < frames; i++)
  wav.writeInt16LE(Math.round(4000 * Math.sin((2 * Math.PI * 440 * i) / rate)), 44 + i * 2);
fs.writeFileSync(fixture, wav);
const tag = Date.now().toString();

(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH }
      : {}),
    args: [
      "--use-fake-device-for-media-stream",
      "--use-fake-ui-for-media-stream",
      `--use-file-for-fake-audio-capture=${fixture}`,
    ],
  });
  const steps = [],
    errors = [];
  let patient,
    posts = 0;
  const wait = async (page, fn, arg) => {
    const end = Date.now() + 30000;
    while (Date.now() < end) {
      if (await page.evaluate(fn, arg)) return;
      await page.waitForTimeout(150);
    }
    throw Error("Voice-note condition timed out");
  };
  const open = async (role, mobile = true, deny = false) => {
    const ctx = await browser.newContext({
      viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 },
      permissions: ["microphone"],
    });
    if (deny)
      await ctx.addInitScript(() => {
        navigator.mediaDevices.getUserMedia = async () => {
          throw new DOMException("Denied for test", "NotAllowedError");
        };
      });
    const p = await ctx.newPage();
    p.on("pageerror", (e) => errors.push(e.message));
    p.on("request", (r) => {
      if (
        r.method() === "POST" &&
        /\/messages\/threads\/[^/]+\/voice$/.test(new URL(r.url()).pathname)
      )
        posts++;
      if (/generativelanguage|api\.meta\.ai|\/voice\/transcribe/.test(r.url()))
        errors.push("Unexpected provider request");
    });
    await p.goto(base + (mobile ? "/mobile/" : "/dashboard/"));
    if (mobile) await p.locator("[name=username]").selectOption(role);
    else await p.locator("[name=username]").fill(role);
    await p.locator("[name=password]").fill(password);
    await p.getByRole("button", { name: "Sign in", exact: true }).click();
    await p
      .getByRole("button", { name: mobile ? "Messages" : "Care messages", exact: true })
      .first()
      .click();
    await p.locator("#care-refresh").waitFor();
    return p;
  };
  const choose = async (p, id) => {
    await p.locator(`[data-care-contact="${id}"]`).click();
    await wait(p, () => !!S.care.thread && !S.care.busy);
  };
  const record = async (p) => {
    await p.locator("#care-voice-record").click();
    await wait(p, () => S.care.voice?.phase === "recording");
    await p.waitForTimeout(900);
    await p.locator("#care-voice-finish").click();
    await wait(p, () => S.care.voice?.phase === "preview");
  };
  try {
    patient = await open("participant");
    await choose(patient, "family");
    await record(patient);
    assert.equal(posts, 0);
    assert.equal(await patient.evaluate(() => S.care.voice.blob.type), "audio/wav");
    await patient.evaluate(async () => {
      const a = document.querySelector("#care-voice audio");
      a.muted = true;
      await a.play();
    });
    await wait(patient, () => document.querySelector("#care-voice audio").currentTime > 0);
    await patient.evaluate(() => document.querySelector("#care-voice audio").pause());
    assert.equal(posts, 0);
    steps.push(
      "real microphone fixture, MediaRecorder and PCM conversion produce local preview without upload",
    );
    const caption = `Synthetic recorded note ${tag}`;
    await patient.locator("#care-voice-form textarea").fill(caption);
    await patient.getByRole("button", { name: "Send voice note", exact: true }).click();
    await wait(patient, () => !S.care.voice && !S.care.busy);
    const row = await patient.evaluate(
      async (text) =>
        (await api(`/patients/${S.pid}/messages/threads/family`)).messages.find(
          (m) => m.body === text,
        ),
      caption,
    );
    assert.equal(row.message_type, "voice");
    assert.equal(row.opened_at, null);
    const family = await open("family");
    await choose(family, "participant");
    const player = family.locator(`audio[src="${row.voice.url}"]`);
    await player.evaluate(async (a) => {
      a.muted = true;
      await a.play();
    });
    await wait(
      family,
      (url) => document.querySelector(`audio[src="${url}"]`).currentTime > 0,
      row.voice.url,
    );
    await player.evaluate((a) => a.pause());
    const stillUnopened = await family.evaluate(
      async (id) =>
        (await api(`/patients/${S.pid}/messages/threads/participant`)).messages.find(
          (m) => m.id === id,
        ).opened_at,
      row.id,
    );
    assert.equal(stillUnopened, null);
    steps.push(
      "explicit Send stores audio; recipient native muted playback decodes it without an opening receipt",
    );
    const doctor = await open("clinician", false);
    await choose(doctor, "participant");
    const denied = await doctor.evaluate(async (url) => (await fetch(url)).status, row.voice.url);
    assert.equal(denied, 404);
    assert.equal(await doctor.locator(`audio[src="${row.voice.url}"]`).count(), 0);
    steps.push("an assigned clinician outside the direct pair cannot fetch the private voice note");
    await record(doctor);
    const doctorCaption = `Synthetic clinician voice ${tag}`;
    await doctor.locator("#care-voice-form textarea").fill(doctorCaption);
    await doctor.getByRole("button", { name: "Send voice note", exact: true }).click();
    await wait(doctor, () => !S.care.voice && !S.care.busy);
    const doctorRow = await doctor.evaluate(
      async (caption) =>
        (await api(`/patients/${S.pid}/messages/threads/participant`)).messages.find(
          (m) => m.body === caption,
        ),
      doctorCaption,
    );
    assert.equal(doctorRow.recipient_id, "participant");
    assert.equal(doctorRow.message_type, "voice");
    steps.push(
      "desktop clinician records and explicitly sends a voice note to the selected patient",
    );
    await family.locator("#care-opened").click();
    await wait(family, () => !S.care.busy);
    await patient.locator("#care-latest").click();
    await wait(patient, () => !S.care.busy);
    assert.equal(
      await patient.evaluate((id) => S.care.thread.messages.find((m) => m.id === id).state, row.id),
      "opened_in_app",
    );
    await record(patient);
    const retryCaption = `Synthetic voice retry ${tag}`;
    await patient.locator("#care-voice-form textarea").fill(retryCaption);
    await patient.evaluate(() => {
      carePolling = true;
    });
    let lost = false;
    await patient.route("**/messages/threads/family/voice", async (route) => {
      if (!lost) {
        lost = true;
        const r = await route.fetch();
        assert.equal(r.status(), 200);
        await route.abort("failed");
      } else await route.continue();
    });
    await patient.getByRole("button", { name: "Send voice note", exact: true }).click();
    await wait(patient, () => S.care.voice?.phase === "unconfirmed" && !S.care.busy);
    const key = await patient.evaluate(() => S.care.voice.command_id);
    assert.equal(await patient.locator("#care-voice-form textarea").isDisabled(), true);
    await patient.getByRole("button", { name: "Retry saving voice note", exact: true }).click();
    await wait(patient, () => !S.care.voice && !S.care.busy);
    const retries = await patient.evaluate(
      async (text) =>
        (await api(`/patients/${S.pid}/messages/threads/family`)).messages.filter(
          (m) => m.body === text,
        ),
      retryCaption,
    );
    assert.equal(retries.length, 1);
    assert.equal(retries[0].command_id, key);
    await patient.evaluate(() => {
      carePolling = false;
    });
    steps.push(
      "committed audio with a lost HTTP response retries unchanged without duplicate messages or clips",
    );
    await patient.locator("#care-voice-record").click();
    await wait(patient, () => S.care.voice?.phase === "recording");
    await patient.evaluate(() => {
      window.testVoiceStream = S.care.voice.stream;
    });
    await patient.getByRole("button", { name: "Home", exact: true }).click();
    assert.equal(
      await patient.evaluate(() =>
        window.testVoiceStream.getTracks().every((t) => t.readyState === "ended"),
      ),
      true,
    );
    await patient.getByRole("button", { name: "Messages", exact: true }).first().click();
    await wait(patient, () => !!S.care.thread);
    assert.equal(await patient.evaluate(() => S.care.voice), null);
    steps.push("navigation cancels an active recording and stops every microphone track");
    await patient.evaluate(() => {
      window.originalGum = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
      navigator.mediaDevices.getUserMedia = async (opts) => {
        const stream = await window.originalGum(opts);
        window.lateStream = stream;
        await new Promise((resolve) => {
          window.releaseVoicePermission = resolve;
        });
        return stream;
      };
    });
    await patient.locator("#care-voice-record").click();
    await wait(patient, () => !!window.releaseVoicePermission);
    await patient.getByRole("button", { name: "Cancel recording", exact: true }).click();
    await patient.evaluate(() => window.releaseVoicePermission());
    await wait(patient, () => window.lateStream.getTracks().every((t) => t.readyState === "ended"));
    await patient.evaluate(() => {
      navigator.mediaDevices.getUserMedia = window.originalGum;
    });
    assert.equal(await patient.evaluate(() => S.care.voice), null);
    steps.push("late microphone permission results are stopped and discarded after cancellation");
    await record(patient);
    const declined = new Promise((resolve) =>
      patient.once("dialog", async (d) => {
        await d.dismiss();
        resolve();
      }),
    );
    await patient.locator("#care-back").click();
    await declined;
    assert.equal(await patient.evaluate(() => S.care.peer), "family");
    assert.equal(await patient.evaluate(() => S.care.voice.phase), "preview");
    steps.push("contact switching requires a decision about the unsent recipient-bound clip");
    const beforeDiscard = posts;
    await patient.getByRole("button", { name: "Discard voice note", exact: true }).click();
    assert.equal(await patient.evaluate(() => S.care.voice), null);
    assert.equal(posts, beforeDiscard);
    const blocked = await open("family", true, true);
    await choose(blocked, "participant");
    await blocked.locator("#care-voice-record").click();
    await blocked
      .getByText(
        "Microphone permission was denied or the device is unavailable. You can use text.",
        { exact: true },
      )
      .waitFor();
    await blocked.locator("#care-compose textarea").fill(`Synthetic text fallback ${tag}`);
    await blocked.getByRole("button", { name: "Send message", exact: true }).click();
    await wait(blocked, () => !S.care.busy && !S.care.drafts.participant);
    steps.push(
      "preview discard performs no upload, and injected permission denial preserves text messaging",
    );
    assert.equal(
      await patient.evaluate(() => document.documentElement.scrollWidth > innerWidth),
      false,
    );
    await patient.screenshot({ path: path.join(out, "voice-notes-mobile.png"), fullPage: true });
    await doctor.screenshot({ path: path.join(out, "voice-notes-dashboard.png"), fullPage: true });
    await doctor.locator(`audio[src="${doctorRow.voice.url}"]`).evaluate(async (a) => {
      window.voiceLogoutPlayer = a;
      a.muted = true;
      await a.play();
    });
    await wait(doctor, () => window.voiceLogoutPlayer.currentTime > 0);
    await doctor.getByRole("button", { name: "Sign out", exact: true }).click();
    await doctor.locator("#login").waitFor();
    assert.equal(await doctor.evaluate(() => window.voiceLogoutPlayer.paused), true);
    assert.equal(await doctor.evaluate(() => S.care.voice), undefined);
    steps.push("sign-out pauses already-playing private audio and clears the voice draft state");
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      path.join(out, "voice-note-browser-check.json"),
      JSON.stringify(
        {
          status: "passed",
          steps,
          errors,
          playback:
            "real native decoding, muted; no speech intelligibility or real-device validation",
          permission_denial: "test double",
          at: new Date().toISOString(),
        },
        null,
        2,
      ),
    );
    console.log(JSON.stringify({ status: "passed", steps, errors }));
  } catch (e) {
    if (patient)
      await patient.screenshot({ path: path.join(out, "voice-notes-failure.png"), fullPage: true });
    console.error("Completed checks:", steps);
    throw e;
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e.stack);
  process.exitCode = 1;
});
