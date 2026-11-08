const { chromium } = require("playwright"),
  fs = require("fs"),
  path = require("path"),
  assert = require("node:assert/strict");
const root = path.resolve(__dirname, ".."),
  base = process.env.NEUROTWIN_BASE_URL;
if (!base || base === "http://127.0.0.1:8140") throw Error("Use the isolated browser runner");
const password = fs
  .readFileSync(path.join(root, ".env"), "utf8")
  .split(/\r?\n/)
  .find((s) => s.startsWith("DEMO_PASSWORD="))
  .slice(14);
const out = path.join(root, "test-results/arabic-ui");
fs.mkdirSync(out, { recursive: true });
const wait = async (page, fn) => {
  const end = Date.now() + 15000;
  while (Date.now() < end) {
    if (await page.evaluate(fn)) return;
    await page.waitForTimeout(75);
  }
  throw Error("Arabic UI did not settle");
};
(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH }
      : {}),
  });
  const errors = [],
    checks = [];
  async function open(role, desktop = false) {
    const context = await browser.newContext({
      viewport: { width: desktop ? 1440 : 390, height: 1000 },
      reducedMotion: "reduce",
    });
    await context.addInitScript(() => {
      localStorage.setItem("neurotwin.locale", "ar");
      window.__spoken = [];
      window.SpeechSynthesisUtterance = class {
        constructor(text) {
          this.text = text;
        }
      };
      Object.defineProperty(window, "speechSynthesis", {
        configurable: true,
        value: {
          getVoices: () => [{ lang: "ar-SA", name: "Arabic synthetic test double" }],
          cancel() {},
          speak(u) {
            window.__spoken.push({ text: u.text, lang: u.lang });
            u.onstart?.();
            setTimeout(() => u.onend?.(), 0);
          },
        },
      });
    });
    const response = await context.request.post(base + "/api/login", {
      data: { username: role, password },
    });
    assert.equal(response.status(), 200);
    const login = await response.json(),
      page = await context.newPage();
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(base + (desktop ? "/dashboard/" : "/mobile/"));
    await page.locator(desktop ? ".topbar" : ".scope").waitFor();
    return { context, page, csrf: login.csrf };
  }
  try {
    const p = await open("participant"),
      c = await open("clinician", true),
      pp = p.page,
      cp = c.page;
    assert.equal(await pp.locator("html").getAttribute("lang"), "ar");
    assert.equal(await pp.locator("html").getAttribute("dir"), "rtl");
    const catalogResponse = await p.context.request.get(base + "/dashboard/ar-catalog.json");
    const canonical = await catalogResponse.json();
    assert.equal(
      await pp.evaluate(
        (c) =>
          Object.keys(c).length === Object.keys(window.NT_AR).length &&
          Object.entries(c).every(([k, v]) => window.NT_AR[k] === v),
        canonical,
      ),
      true,
    );
    assert.equal(
      await pp.evaluate(() => {
        localStorage.setItem("neurotwin.locale", "en");
        const active = ntLocale();
        localStorage.setItem("neurotwin.locale", "ar");
        return active;
      }),
      "ar",
    );
    assert.match(await pp.locator("body").innerText(), /[\u0600-\u06ff]/);
    const privateText = await pp.evaluate(() => ntUi`<p>${"Settings"}</p>`);
    assert.equal(privateText, "<p>Settings</p>");
    const attrs = await pp.evaluate(
      () =>
        ntUi`<button data-id="${"Settings"}" class="card" aria-label="Settings">Settings</button>`,
    );
    assert.match(attrs, /data-id="Settings"/);
    assert.match(attrs, /class="card"/);
    assert.match(attrs, /[\u0600-\u06ff]/);
    checks.push(
      "Persisted Arabic locale, semantic RTL and static-only translation without changing data or attributes",
    );
    for (const tab of ["home", "plan", "check", "support", "companion", "settings"]) {
      if (await pp.locator(`[data-tab="${tab}"]:visible`).count())
        await pp.locator(`[data-tab="${tab}"]:visible`).first().click();
      else
        await pp.evaluate((t) => {
          S.tab = t;
          render();
        }, tab);
      for (const width of [320, 390, 768, 1440]) {
        await pp.setViewportSize({ width, height: 1000 });
        assert.equal(
          await pp.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
          false,
          `Overflow ${tab} ${width}`,
        );
      }
      await pp.setViewportSize({ width: 320, height: 1000 });
      await pp.evaluate(() => {
        document.documentElement.style.fontSize = "32px";
        document.documentElement.classList.add("large");
      });
      assert.equal(
        await pp.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
        false,
        `Large text overflow ${tab}`,
      );
      await pp.evaluate(() => {
        document.documentElement.style.fontSize = "";
        document.documentElement.classList.remove("large");
      });
    }
    await pp.screenshot({ path: path.join(out, "settings-rtl.png"), fullPage: true });
    checks.push("Six mobile pages at four viewport widths and enlarged root text");
    await pp.evaluate(() => {
      S.tab = "companion";
      render();
    });
    await pp.locator("#chatInput").fill("افتح الإعدادات");
    await pp.locator("#chat button[type=submit], #chat button.primary").first().click();
    await wait(pp, () => S.tab === "settings" && !S.busy);
    assert(
      await pp.evaluate(() =>
        window.__spoken.some((s) => s.lang === "ar-SA" && /[\u0600-\u06ff]/.test(s.text)),
      ),
    );
    await pp.evaluate(() => {
      S.tab = "companion";
      render();
    });
    await pp.locator("#chatInput").fill("كبر الخط");
    await pp.locator("#chat button.primary").click();
    await pp.locator("#confirmCompanion").waitFor();
    assert.equal(await pp.evaluate(() => S.pendingAction.requires_confirmation), true);
    await pp.locator("#cancelCompanion").click();
    await pp.locator("#chatInput").fill("لا تفتح الإعدادات");
    await pp.locator("#chat button.primary").click();
    await wait(pp, () => !S.busy);
    assert.equal(await pp.evaluate(() => S.tab), "companion");
    const count = await pp.evaluate(() => window.__spoken.length);
    await pp.evaluate(() => {
      window.speechSynthesis.getVoices = () => [];
      speakReply("سأفتح الإعدادات.");
    });
    assert.equal(await pp.evaluate(() => S.voiceState), "error");
    assert.equal(await pp.evaluate(() => window.__spoken.length), count);
    checks.push(
      "Arabic command proposals and spoken language, explicit change confirmation, negation and no-voice text fallback (speech test double)",
    );
    await cp.locator('[data-tab="patient"]').first().click();
    await cp.locator("[data-model-evaluation]").click();
    await wait(cp, () => document.querySelector("[data-model-content] table") !== null);
    assert.match(await cp.locator(".model-benchmark").innerText(), /0\.833/);
    await cp.setViewportSize({ width: 768, height: 1000 });
    assert.equal(
      await cp.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
      false,
    );
    await cp.screenshot({ path: path.join(out, "clinical-model-rtl.png"), fullPage: true });
    checks.push("Read-only original-cohort model evaluation in Arabic clinical dashboard");
    const assignment = await c.context.request.post(
      base + "/api/patients/patient-demo/assessments",
      {
        headers: { "X-CSRF-Token": c.csrf },
        data: {
          command_id: crypto.randomUUID(),
          protocol_version: "1.0",
          timezone: "Asia/Dubai",
          location: "Dubai",
          acknowledge_adaptation: true,
        },
      },
    );
    assert.equal(assignment.status(), 200);
    await pp.evaluate(() => {
      S.tab = "check";
      render();
    });
    await pp.locator("[data-assessment-consent]").waitFor();
    assert.equal(
      await pp
        .locator("[data-assessment-consent]")
        .locator("xpath=preceding-sibling::p[1]")
        .getAttribute("lang"),
      "en",
    );
    assert.match(await pp.locator(".assessment-language-notice").innerText(), /[\u0600-\u06ff]/);
    assert.equal(await pp.locator(".iot-panel").count(), 0);
    assert.equal(
      (await p.context.request.get(base + "/dashboard/iot-simulation.js")).status(),
      404,
    );
    checks.push(
      "English research consent retained with Arabic language notice; retired feature unavailable",
    );
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      path.join(out, "report.json"),
      JSON.stringify(
        {
          checks,
          console_errors: errors,
          real_speech_evaluation: false,
          qualified_language_review: false,
        },
        null,
        2,
      ),
    );
    console.log(JSON.stringify({ passed: checks.length, console_errors: errors }));
  } catch (error) {
    const page = browser.contexts()[0]?.pages()[0];
    if (page) {
      await page.screenshot({ path: path.join(out, "failure.png"), fullPage: true });
      const overflow = await page.evaluate(() =>
        [...document.querySelectorAll("body *")]
          .filter((el) => el.getClientRects().length)
          .map((el) => ({
            tag: el.tagName,
            cls: String(el.className).slice(0, 120),
            left: el.getBoundingClientRect().left,
            right: el.getBoundingClientRect().right,
            width: el.getBoundingClientRect().width,
          }))
          .filter((x) => x.left < -1 || x.right > innerWidth + 1)
          .slice(0, 35),
      );
      fs.writeFileSync(path.join(out, "overflow.json"), JSON.stringify(overflow, null, 2));
    }
    throw error;
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
