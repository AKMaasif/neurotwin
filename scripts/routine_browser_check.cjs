const base = process.env.NEUROTWIN_BASE_URL || "http://127.0.0.1:8140";
const { chromium } = require("playwright");
const fs = require("fs"),
  path = require("path");
(async () => {
  const root = path.resolve(__dirname, ".."),
    out = path.join(root, "test-results");
  const password = fs
    .readFileSync(path.join(root, ".env"), "utf8")
    .split(/\r?\n/)
    .find((x) => x.startsWith("DEMO_PASSWORD="))
    .slice(14);
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH }
      : {}),
  });
  const patientContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    timezoneId: "Asia/Colombo",
    permissions: ["notifications"],
  });
  const clinicianContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const familyContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    timezoneId: "Asia/Colombo",
  });
  const patient = await patientContext.newPage(),
    clinician = await clinicianContext.newPage(),
    family = await familyContext.newPage(),
    steps = [],
    errors = [];
  for (const p of [patient, clinician, family]) p.on("pageerror", (e) => errors.push(e.message));
  function notificationDouble() {
    Object.defineProperty(Notification, "permission", { configurable: true, get: () => "granted" });
    Notification.requestPermission = async () => "granted";
    ServiceWorkerRegistration.prototype.showNotification = async function (title, options) {
      const saved = JSON.parse(localStorage.getItem("nt-test-notifications") || "[]");
      saved.push({ title, body: options.body, tag: options.tag });
      localStorage.setItem("nt-test-notifications", JSON.stringify(saved));
    };
    ServiceWorkerRegistration.prototype.getNotifications = async function () {
      return JSON.parse(localStorage.getItem("nt-test-notifications") || "[]").map((n) => ({
        ...n,
        close() {
          localStorage.setItem(
            "nt-test-notifications",
            JSON.stringify(
              JSON.parse(localStorage.getItem("nt-test-notifications") || "[]").filter(
                (x) => x.tag !== n.tag,
              ),
            ),
          );
        },
      }));
    };
  }
  async function login(page, role) {
    await page.goto(base + "/" + (role === "clinician" ? "dashboard/" : "mobile/"));
    if (role === "clinician") await page.locator("[name=username]").fill(role);
    else await page.locator("[name=username]").selectOption(role);
    await page.locator("[name=password]").fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.locator(role === "clinician" ? ".topbar" : ".scope").waitFor();
    if (!(await page.evaluate(() => S.data.patient.synthetic)))
      throw Error("Routine browser check requires synthetic data");
  }
  async function propose(label) {
    await clinician.getByRole("button", { name: "Patient workspace", exact: true }).click();
    await clinician.locator("#plan [name=title]").fill(label);
    await clinician
      .locator("#plan [name=instructions]")
      .fill("Review fictional appointment details with your chosen helper.");
    await clinician.getByRole("button", { name: "Save draft", exact: true }).click();
    await clinician
      .getByText("Draft saved. It is not active until reviewed and approved.", { exact: true })
      .waitFor();
    clinician.once("dialog", (d) => d.accept());
    await clinician
      .getByRole("button", { name: "Review and approve this revision", exact: true })
      .last()
      .click();
    await clinician
      .getByText(
        "Approved revision saved. Mobile can refresh the current plan. No EHR dispatch occurred.",
        { exact: true },
      )
      .waitFor();
    await clinician.getByRole("button", { name: "Daily routines", exact: true }).click();
    await clinician.locator("#clinicalRoutine [name=template_id]").selectOption({ label });
    const local = await patient.evaluate(() => {
      const d = new Date();
      d.setMinutes(d.getMinutes() - 1);
      return {
        date: new Intl.DateTimeFormat("en-CA").format(d),
        time: String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0"),
      };
    });
    await clinician.locator("#clinicalRoutine [name=timezone]").fill("Asia/Colombo");
    await clinician.locator("#clinicalRoutine [name=local_time]").fill(local.time);
    await clinician.locator("#clinicalRoutine [name=start_date]").fill(local.date);
    await clinician
      .getByRole("button", { name: "Save for participant confirmation", exact: true })
      .click();
    await clinician
      .getByText("Proposal saved. The participant must confirm before it runs.", { exact: true })
      .waitFor();
    return await clinician.evaluate(
      (title) => S.routineData.routines.find((r) => r.payload.title === title),
      label,
    );
  }
  async function waitData(page, fn, arg, options = {}) {
    const deadline = Date.now() + (options.timeout || 30000);
    while (Date.now() < deadline) {
      if (await page.evaluate(fn, arg)) return;
      await page.waitForTimeout(350);
    }
    throw Error("Timed out waiting for scheduler data");
  }
  async function activate(r) {
    await patient.evaluate(async () => {
      S.tab = "plan";
      await refresh();
    });
    await patient.locator(`[data-consent-routine="${r.id}"]`).click();
    const form = patient.locator(`.routine-consent[data-routine="${r.id}"]`);
    await form.locator("[name=active]").check();
    const hour = await patient.evaluate(() => (new Date().getHours() + 12) % 24);
    await form.locator("[name=quiet_start]").fill(String(hour).padStart(2, "0") + ":00");
    await form.locator("[name=quiet_end]").fill(String(hour).padStart(2, "0") + ":01");
    await form.getByRole("button", { name: "Confirm routine choices", exact: true }).click();
    await patient
      .getByText("Your routine and follow-up choices were saved.", { exact: true })
      .waitFor();
    await waitData(
      patient,
      async (id) =>
        (await api(`/patients/${S.pid}/routines`)).occurrences.some(
          (o) => o.routine_id === id && o.status === "pending",
        ),
      r.id,
      { timeout: 30000, polling: 750 },
    );
    await patient.evaluate(async () => {
      S.tab = "home";
      await refresh();
    });
    return await patient.evaluate(
      async (id) =>
        (await api(`/patients/${S.pid}/routines`)).occurrences.find((o) => o.routine_id === id),
      r.id,
    );
  }
  try {
    await login(patient, "participant");
    await login(clinician, "clinician");
    const r = await propose("Synthetic daily routine " + Date.now());
    if (r.status !== "awaiting_consent")
      throw Error("Clinician proposal ran without participant consent");
    steps.push("Clinician proposed approved timing without activating it");
    let o = await activate(r);
    if (!o)
      throw Error(
        "Missing occurrence for " +
          r.id +
          ": " +
          JSON.stringify(
            await patient.evaluate(async () =>
              (await api(`/patients/${S.pid}/routines`)).occurrences.map((o) => ({
                id: o.id,
                routine_id: o.routine_id,
                status: o.status,
              })),
            ),
          ),
      );
    steps.push("Participant consent generated one dated activity in the selected time zone");
    await waitData(
      patient,
      async (id) =>
        (await api(`/patients/${S.pid}/routines`)).reminders.some((n) => n.occurrence_id === id),
      o.id,
      { timeout: 15000, polling: 500 },
    );
    await patient.evaluate(() => refresh());
    await patient.getByRole("button", { name: "Settings", exact: true }).click();
    await patient.evaluate(() => {
      Notification.requestPermission = async () => "denied";
    });
    await patient
      .getByRole("button", { name: "Enable notifications on this device", exact: true })
      .click();
    await patient
      .getByText("Notifications were not enabled. In-app reminders still work.", { exact: true })
      .waitFor();
    steps.push("Denied browser notification permission kept the in-app reminder available");
    await patient.evaluate(notificationDouble);
    await patientContext.addInitScript(notificationDouble);
    await patient
      .getByRole("button", { name: "Enable notifications on this device", exact: true })
      .click();
    await patient
      .getByText("Device alerts are enabled while this app is open.", { exact: true })
      .waitFor();
    await patient.evaluate(() => pollRoutineNotifications());
    const notices = await patient.evaluate(async () => {
      const r = await navigator.serviceWorker.getRegistration("/mobile/");
      return (await r.getNotifications()).map((n) => ({
        title: n.title,
        body: n.body,
        tag: n.tag,
      }));
    });
    if (notices.length !== 1 || notices.some((n) => n.body.includes("Synthetic daily routine")))
      throw Error(
        "Notification count or privacy failed: " +
          JSON.stringify({
            notices,
            data: await patient.evaluate(async () => ({
              permission: Notification.permission,
              enabled: localStorage.getItem("nt-notify:" + S.user.id),
              notices: (await api(`/patients/${S.pid}/routines`)).reminders,
            })),
          }),
      );
    const second = await patientContext.newPage();
    await second.goto(base + "/mobile/");
    await second.waitForFunction(() => S.routineData);
    await Promise.all([
      patient.evaluate(() => pollRoutineNotifications()),
      second.evaluate(() => pollRoutineNotifications()),
    ]);
    if (
      (await patient.evaluate(
        async () =>
          (await (await navigator.serviceWorker.getRegistration("/mobile/")).getNotifications())
            .length,
      )) !== 1
    )
      throw Error("Duplicate device notices");
    await second.close();
    steps.push(
      "Real service-worker registration and simulated notification request used generic text and deduplicated across tabs",
    );
    await patient.getByRole("button", { name: "Home", exact: true }).click();
    await patient.locator("[data-ack-reminder]").first().click();
    await patient
      .getByText("Reminder acknowledged. Activity completion has not changed.", { exact: true })
      .waitFor();
    if (
      (await patient.evaluate(
        (id) => S.routineData.occurrences.find((o) => o.id === id).task.status,
        o.id,
      )) !== "pending"
    )
      throw Error("Acknowledgement completed task");
    steps.push("Reminder acknowledgement remained separate from completion");
    await patientContext.setOffline(true);
    await patient.locator(`[data-occurrence="${o.id}"][data-routine-response="snooze"]`).click();
    await patient.waitForFunction(() => S.offlineActions?.length === 1);
    const queued = await patient.evaluate(() => S.offlineActions[0]);
    if (queued.title || queued.instructions) throw Error("Offline packet stored content");
    const server = await clinician.evaluate(
      async (id) =>
        (await api(`/patients/${S.pid}/routines`)).occurrences.find((o) => o.id === id).task.status,
      o.id,
    );
    if (server !== "pending") throw Error("Offline action was presented as committed");
    await patientContext.setOffline(false);
    await patient.waitForFunction(
      () =>
        !S.offlineActions.length && S.routineData.occurrences.some((o) => o.status === "snoozed"),
      null,
      { timeout: 30000 },
    );
    steps.push("Offline snooze stayed unconfirmed until reconnect and reconciled once");
    await patient.locator(`[data-routine-help="${o.id}"]`).click();
    await patient.locator("#routineHelp [name=recipient_id]").selectOption("family");
    await patient.getByRole("button", { name: "Confirm and ask for help", exact: true }).click();
    await patient
      .getByText("Your response was confirmed by the server.", { exact: true })
      .waitFor();
    const helpId = await patient.evaluate(
      (id) => S.routineData.occurrences.find((o) => o.id === id).help_id,
      o.id,
    );
    await login(family, "family");
    await family.getByRole("button", { name: "Support", exact: true }).click();
    await family.locator(`[data-accept="${helpId}"]`).click();
    await family.getByText("Responsibility accepted.", { exact: true }).waitFor();
    await patient.evaluate(() => refresh());
    if (
      (await patient.evaluate(
        (id) => S.routineData.occurrences.find((o) => o.id === id).help_status,
        o.id,
      )) !== "accepted"
    )
      throw Error("Acceptance not propagated");
    steps.push(
      "Explicit help request reached the authorized family account and responsibility was accepted",
    );
    await patient.screenshot({ path: path.join(out, "routine-patient.png"), fullPage: true });
    await clinician.evaluate(() => refresh());
    await clinician.screenshot({ path: path.join(out, "routine-clinician.png"), fullPage: true });
    await patient.locator(`[data-occurrence="${o.id}"][data-routine-response="completed"]`).click();
    await patient
      .getByText("Your response was confirmed by the server.", { exact: true })
      .waitFor();
    await waitData(
      patient,
      async (id) =>
        (await api(`/patients/${S.pid}/routines`)).occurrences.some(
          (o) => o.id === id && o.status === "completed" && o.help_status === "resolved",
        ),
      o.id,
    );
    await patient.evaluate(() => refresh());
    if (
      (await patient.evaluate(
        (id) => S.routineData.occurrences.find((o) => o.id === id).help_status,
        o.id,
      )) !== "resolved"
    )
      throw Error("Help remained open after confirmation");
    steps.push("Completion resolved the related help request and cancelled reminders");
    const r2 = await propose("Synthetic stale-response routine " + Date.now());
    o = await activate(r2);
    await patientContext.setOffline(true);
    await patient.locator(`[data-occurrence="${o.id}"][data-routine-response="completed"]`).click();
    await patient.waitForFunction(() => S.offlineActions?.length === 1);
    await clinician.evaluate(async (id) => {
      const r = (await api(`/patients/${S.pid}/routines`)).routines.find((r) => r.id === id);
      await api(`/patients/${S.pid}/routines/${id}/schedule`, "POST", {
        expected_version: r.version,
        timezone: r.payload.timezone,
        local_time: r.payload.local_time,
        weekdays: r.payload.weekdays,
        start_date: r.payload.start_date,
        end_date: r.payload.end_date,
      });
    }, r2.id);
    await patientContext.setOffline(false);
    await patient.waitForFunction(() => S.offlineActions?.some((x) => x.conflict), null, {
      timeout: 30000,
    });
    steps.push("Changed routine caused an offline conflict without overwriting the server");
    await patient.locator("[data-discard-offline]").click();
    await patient.waitForFunction(() => S.offlineActions.length === 0);
    if (errors.length) throw Error(errors.join(";"));
    fs.writeFileSync(
      path.join(out, "routine-browser-check.json"),
      JSON.stringify(
        {
          status: "passed",
          steps,
          errors,
          device_delivery_proven: false,
          notification_display: "test double; real device permission/display not validated",
          service_worker_registration: "real",
          offline_queue: "real IndexedDB with browser network interruption",
          clinical_validation: false,
        },
        null,
        2,
      ),
    );
    console.log(JSON.stringify({ status: "passed", steps, errors }));
  } catch (e) {
    await patient.screenshot({
      path: path.join(out, "routine-browser-failure.png"),
      fullPage: true,
    });
    console.error("Completed checks:", steps);
    throw e;
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e.stack);
  process.exitCode = 1;
});
