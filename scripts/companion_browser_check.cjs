const baseUrl = process.env.NEUROTWIN_BASE_URL || "http://127.0.0.1:8140";
const { chromium } = require("playwright");
const fs = require("fs"),
  path = require("path");
(async () => {
  const root = path.resolve(__dirname, ".."),
    out = path.join(root, "test-results");
  fs.mkdirSync(out, { recursive: true });
  const password = fs
    .readFileSync(path.join(root, ".env"), "utf8")
    .split(/\r?\n/)
    .find((x) => x.startsWith("DEMO_PASSWORD="))
    .slice(14);
  const b = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH }
      : {}),
    args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"],
  });
  const context = await b.newContext({
    viewport: { width: 390, height: 844 },
    permissions: ["microphone"],
  });
  const p = await context.newPage(),
    steps = [],
    errors = [];
  p.on("pageerror", (e) => errors.push(e.message));
  await context.addInitScript(() => {
    Object.defineProperty(window, "speechSynthesis", {
      value: {
        cancel() {},
        speak(u) {
          u.onstart?.();
          setTimeout(() => u.onend?.(), 20);
        },
      },
    });
  });
  let audioRequests = 0;
  try {
    await p.goto(baseUrl + "/mobile/");
    await p.locator("[name=password]").fill(password);
    await p.getByRole("button", { name: "Sign in", exact: true }).click();
    await p.getByRole("button", { name: "Companion", exact: true }).click();
    await p.route("**/voice/transcribe", async (route) => {
      audioRequests++;
      const data = route.request().postDataBuffer();
      if (!data.includes(Buffer.from("RIFF")) || !data.includes(Buffer.from("WAVE")))
        throw Error("Expected real PCM WAV conversion");
      await route.fulfill({ json: { text: "Open settings", audio_retained: false } });
    });
    await p.getByRole("button", { name: "Speak", exact: true }).click();
    await p.waitForFunction(() => S.voiceState === "listening");
    await p.waitForTimeout(700);
    await p.getByRole("button", { name: "Finish recording", exact: true }).click();
    await p.waitForFunction(() => S.voiceState === "transcript_ready");
    if ((await p.locator("#chatInput").inputValue()) !== "Open settings")
      throw Error("Missing reviewed transcript");
    if ((await p.evaluate(() => S.tab)) !== "companion")
      throw Error("Voice auto-executed before Send");
    steps.push(
      "Real MediaRecorder and PCM conversion reached mocked ASR; transcript required Send",
    );
    await p.getByRole("button", { name: "Send", exact: true }).click();
    await p.getByRole("heading", { name: "Settings", exact: true }).waitFor();
    await p.locator("#memorySettings [name=enabled]").check();
    await p.locator("#memorySettings [name=preferred_name]").fill("Preferred synthetic name");
    await p.locator("#memorySettings [name=speech_rate]").selectOption("slow");
    await p.getByRole("button", { name: "Save memory choices", exact: true }).click();
    await p.getByText("Your memory choices were saved.", { exact: true }).waitFor();
    await p.getByRole("button", { name: "Companion", exact: true }).click();
    await p.locator("#chatInput").fill("read my plan");
    await p.getByRole("button", { name: "Send", exact: true }).click();
    await p.waitForFunction(() => !S.busy && S.chat.some((c) => c.role === "bot"));
    await p.reload();
    await p.getByRole("button", { name: "Companion", exact: true }).click();
    await p.waitForFunction(() => S.memory?.enabled && S.chat.length > 0);
    steps.push("Opt-in preferences and bounded conversation survived reload");
    await p.getByRole("button", { name: "Guide my next activity", exact: true }).click();
    await p.locator(".step-guide").waitFor();
    await p.screenshot({ path: path.join(out, "companion-activity-guide.png"), fullPage: true });
    await p.evaluate(() => stopCompanion(false));
    await p
      .locator('[data-say="I finished"]')
      .count()
      .then(async (n) => {
        if (!n) {
          while (await p.locator('[data-say="next step"]').count()) {
            await p.locator('[data-say="next step"]').click();
            await p.waitForFunction(() => !S.busy);
          }
        }
      });
    await p.locator('[data-say="I finished"]').click();
    await p.locator("#confirmCompanion").waitFor();
    const task = await p.evaluate(() => S.pendingAction.task);
    if (
      !(await p.evaluate(
        async (id) =>
          (await api(`/patients/${S.pid}/workspace`)).records.find((x) => x.id === id).status !==
          "completed",
        task.id,
      ))
    )
      throw Error("Unconfirmed activity changed");
    await p.getByRole("button", { name: "Cancel change", exact: true }).click();
    steps.push("Approved activity guidance proposed completion without saving before confirmation");
    await p.locator('[data-say="I finished"]').click();
    await p.locator("#confirmCompanion").waitFor();
    await p.getByRole("button", { name: "Confirm", exact: true }).click();
    await p.getByText("Your confirmed change was saved.", { exact: true }).waitFor();
    if (
      !(await p.evaluate(
        async (id) =>
          (await api(`/patients/${S.pid}/workspace`)).records.find((t) => t.id === id).status ===
          "completed",
        task.id,
      ))
    )
      throw Error("Confirmed activity was not saved");
    steps.push("Confirmed activity completion persisted through the existing versioned task API");
    await p.locator("#chatInput").fill("make text larger");
    await p.getByRole("button", { name: "Send", exact: true }).click();
    await p.locator("#confirmCompanion").waitFor();
    await p.getByRole("button", { name: "Confirm", exact: true }).click();
    await p.getByText("Your confirmed change was saved.", { exact: true }).waitFor();
    await p.waitForFunction(() => document.documentElement.classList.contains("large"));
    if (!(await p.evaluate(() => document.documentElement.classList.contains("large"))))
      throw Error("Confirmed size not applied");
    steps.push("Explicit confirmation saved the text-size preference");
    const before = audioRequests;
    await p.getByRole("button", { name: "Speak", exact: true }).click();
    await p.waitForFunction(() => S.recording);
    await p.evaluate(() => S.micStream.getTracks()[0].dispatchEvent(new Event("ended")));
    await p.waitForFunction(() => S.voiceState === "error");
    if (audioRequests !== before) throw Error("Interrupted recording was uploaded");
    steps.push("Interrupted microphone recording stopped tracks and discarded audio");
    await p.unroute("**/voice/transcribe");
    let release, received;
    const got = new Promise((r) => (received = r)),
      hold = new Promise((r) => (release = r));
    await p.route("**/voice/transcribe", async (route) => {
      received();
      await hold;
      await route
        .fulfill({ json: { text: "Open settings", audio_retained: false } })
        .catch(() => {});
    });
    await p.getByRole("button", { name: "Speak", exact: true }).click();
    await p.waitForFunction(() => S.recording);
    await p.waitForTimeout(500);
    await p.getByRole("button", { name: "Finish recording", exact: true }).click();
    await got;
    await p.getByRole("button", { name: "Stop", exact: true }).click();
    release();
    await p.waitForTimeout(400);
    if (await p.evaluate(() => S.draftText === "Open settings" || S.recording || S.busy))
      throw Error("Stopped ASR response changed state");
    steps.push("Stop discarded a delayed ASR reply");
    await p.route("**/companion", (route) => route.abort("failed"));
    await p.locator("#chatInput").fill("Open settings");
    await p.getByRole("button", { name: "Send", exact: true }).click();
    await p.locator("#retryCompanion").waitFor();
    await p.unroute("**/companion");
    await p.getByRole("button", { name: "Retry request", exact: true }).click();
    await p.getByRole("heading", { name: "Settings", exact: true }).waitFor();
    steps.push("Network failure preserved the typed request and allowed retry");
    await p
      .getByRole("button", { name: "Forget conversations and preferences", exact: true })
      .click();
    await p
      .getByText("Conversation memory and preferences were cleared.", { exact: true })
      .waitFor();
    if (await p.evaluate(() => S.memory.enabled || S.chat.length))
      throw Error("Memory was not cleared");
    steps.push("Forget reset server memory and local conversation");
    await p.getByRole("button", { name: "Companion", exact: true }).click();
    await p.screenshot({ path: path.join(out, "companion-mobile.png"), fullPage: true });
    if (await p.evaluate(() => document.documentElement.scrollWidth > innerWidth))
      throw Error("Horizontal mobile overflow");
    await p.evaluate(() => {
      navigator.mediaDevices.getUserMedia = async () => {
        throw new DOMException("Denied", "NotAllowedError");
      };
    });
    await p.getByRole("button", { name: "Speak", exact: true }).click();
    await p.waitForFunction(() => S.voiceState === "error" && !S.busy);
    await p.locator("#chatInput").fill("Open home");
    await p.getByRole("button", { name: "Send", exact: true }).click();
    await p.locator(".home-heading h1").waitFor();
    steps.push("Denied microphone permission retained working text navigation");
    if (errors.length) throw Error(errors.join(";"));
    fs.writeFileSync(
      path.join(out, "companion-browser-check.json"),
      JSON.stringify(
        {
          status: "passed",
          steps,
          errors,
          audio_source: "Chromium synthetic microphone",
          asr: "mocked response, not speech accuracy validation",
          speech_output: "test double",
          clinical_validation: false,
        },
        null,
        2,
      ),
    );
    console.log(JSON.stringify({ status: "passed", steps, errors }));
  } catch (e) {
    await p.screenshot({ path: path.join(out, "companion-browser-failure.png"), fullPage: true });
    console.error("Completed checks:", steps);
    throw e;
  } finally {
    await b.close();
  }
})().catch((e) => {
  console.error(e.message);
  process.exitCode = 1;
});
