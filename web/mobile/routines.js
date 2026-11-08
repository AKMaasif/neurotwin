async function updateRoutineData() {
  const epoch = (S.routineRequest = (S.routineRequest || 0) + 1),
    actor = S.user?.id,
    pid = S.pid;
  const data = await api(`/patients/${pid}/routines`);
  if (epoch !== S.routineRequest || S.user?.id !== actor || S.pid !== pid) return false;
  S.routineData = data;
  return true;
}
function routineTime(value, zone) {
  return new Intl.DateTimeFormat(ntLocale() === "ar" ? "ar-AE" : "en", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: zone,
  }).format(new Date(value));
}
function activeOccurrence(o) {
  return !["completed", "skipped", "cancelled", "expired"].includes(o.status);
}
function renderDailyActivities(limit = null) {
  const data = S.routineData;
  if (!data) return "";
  const family = S.user.role === "family";
  const notices = data.reminders.filter((n) => n.state !== "acknowledged");
  const selectedOccurrences = family
    ? data.occurrences.filter((o) => notices.some((n) => n.occurrence_id === o.id))
    : data.occurrences.filter(activeOccurrence).slice(0, 4);
  const occurrences = limit ? selectedOccurrences.slice(0, limit) : selectedOccurrences;
  return `${S.offlineActions?.length ? ntUi`<section class="card offline-actions" role="status"><h2>${S.offlineActions.length} response(s) saved on this device</h2><p>They are not confirmed by the server yet.</p>${S.offlineActions.map((x) => ntUi`<p>${x.conflict ? ntTr("Needs review: the activity or your access changed.") : ntTr("Waiting to reconnect.")} <button data-discard-offline="${x.id}">Discard queued response</button></p>`).join("")}</section>` : ""}${occurrences
    .map((o) => {
      const r = data.routines.find((r) => r.id === o.routine_id),
        ns = notices.filter((n) => n.occurrence_id === o.id);
      return ntUi`<section class="card routine-activity ${ns.length ? "hero" : ""}"><div class="eyebrow">${family ? ntTr("FAMILY FOLLOW-UP") : ntTr("DATED ACTIVITY")} · ${esc(o.local_date)}</div><h2>${esc(o.task.title)}</h2><p>${esc(routineTime(o.scheduled_at, r.payload.timezone))}<br><span class="muted">${esc(r.payload.timezone)}</span></p><p>${family ? ntTr("The activity has not been confirmed. This does not prove it was missed.") : o.status === "snoozed" ? "Remind again at " + esc(routineTime(o.reminder_at, r.payload.timezone)) : ntTr("Not yet confirmed by you.")}</p>${o.resolution === "shifted_to_valid_minute" ? ntUi('<p class="muted">Adjusted to the first valid local minute because the clock changed.</p>') : ""}${!family && S.data.scopes.includes("respond") ? ntUi`<div class="actions"><button class="primary" data-routine-response="completed" data-occurrence="${o.id}">Done</button><button data-routine-response="snooze" data-occurrence="${o.id}">Remind me in 15 minutes</button><button data-routine-help="${o.id}">Ask for help</button></div>` : ""}${ns.map((n) => ntUi`<div class="reminder-evidence"><p class="muted">Reminder: ${esc(n.state.replaceAll("_", " "))}${n.device_states.length ? " · Browser: " + esc(n.device_states.join(", ")) : ""}</p><button data-ack-reminder="${n.id}">I have seen this reminder</button><p class="muted">Acknowledging does not complete the activity.</p></div>`).join("")}${o.help_status ? ntUi`<p class="muted">Help request: ${esc(o.help_status)}${o.help_status === "requested" ? " · no responsibility accepted yet" : ""}</p>` : ""}${family ? ntUi('<button data-tab="support">Review and accept the help request</button>') : ""}</section>`;
    })
    .join("")}${S.helpOccurrence ? renderRoutineHelp() : ""}`;
}
function renderRoutineHelp() {
  const family = S.contacts.filter((c) => c.role === "family");
  return ntUi`<section class="card"><h2>Who would you like help from?</h2><form id="routineHelp"><label>Family contact<select name="recipient_id" required>${family.map((c) => ntUi`<option value="${esc(c.id)}">${esc(c.name)}</option>`).join("")}</select></label><button class="primary" ${family.length ? "" : "disabled"}>Confirm and ask for help</button><button type="button" id="cancelRoutineHelp">Cancel</button></form>${family.length ? "" : ntUi("<p>No authorized family contact is available. Ask your care team to review sharing.</p>")}</section>`;
}
function scheduleFields(value = {}) {
  const zone = value.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Dubai";
  const date = new Intl.DateTimeFormat("en-CA", {
    timeZone: zone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
  const end = new Date();
  end.setDate(end.getDate() + 30);
  return ntUi`<label>Time zone<input name="timezone" value="${esc(zone)}" list="timezones" required><datalist id="timezones"><option>Asia/Dubai</option><option>Asia/Riyadh</option><option>Asia/Colombo</option></datalist></label><label>Local reminder time<input name="local_time" type="time" value="${esc(value.local_time || "09:00")}" required></label><div class="schedule-dates"><label>Start date<input name="start_date" type="date" value="${esc(value.start_date || date)}" required></label><label>End date<input name="end_date" type="date" value="${esc(value.end_date || end.toISOString().slice(0, 10))}" required></label></div><fieldset><legend>Days</legend><div class="weekday-options">${["Mon", ntTr("Tue"), ntTr("Wed"), ntTr("Thu"), ntTr("Fri"), ntTr("Sat"), ntTr("Sun")].map((d, i) => ntUi`<label><input type="checkbox" name="weekdays" value="${i}" ${(value.weekdays || [0, 1, 2, 3, 4, 5, 6]).includes(i) ? "checked" : ""}>${d}</label>`).join("")}</div></fieldset>`;
}
function scheduleBody(form) {
  const f = new FormData(form);
  return {
    timezone: f.get("timezone"),
    local_time: f.get("local_time"),
    start_date: f.get("start_date"),
    end_date: f.get("end_date"),
    weekdays: f.getAll("weekdays").map(Number),
  };
}
function renderRoutineManager() {
  if (!S.routineData || S.user.role !== "participant") return "";
  const routines = S.routineData.routines.filter((r) => r.status !== "review_required"),
    templates = records("task").filter(
      (t) =>
        !t.payload.occurrence_id &&
        records("plan").some(
          (p) =>
            p.id === t.payload.plan_id &&
            p.status === "approved" &&
            !p.payload.source_review_required,
        ),
    );
  return ntUi`<section class="card routine-manager"><h2>Daily routines</h2><p>Use approved activities at the times you choose. Alerts here require the app to be open; the reminder worker runs on the server.</p><div class="reference-routine-filters" role="group" aria-label="Filter scheduled routines">${[
    ["all", ntTr("All"), routines.length],
    [
      "awaiting_consent",
      ntTr("Awaiting"),
      routines.filter((r) => r.status === "awaiting_consent").length,
    ],
    ["active", ntTr("Active"), routines.filter((r) => r.status === "active").length],
  ]
    .map(
      ([state, label, count]) =>
        ntUi`<button data-routine-filter="${state}" aria-pressed="${(S.routineFilter || "all") === state}">${label} (${count})</button>`,
    )
    .join(
      "",
    )}</div><p class="routine-filter-empty" role="status" hidden>No routines match this filter.</p><div class="routine-list">${routines.map((r) => ntUi`<article class="routine-row" data-routine-state="${esc(r.status)}"><h3><span class="routine-title-icon" aria-hidden="true">${icon("plan")}</span>${esc(r.payload.title)}</h3><details class="routine-details"><summary aria-label="Routine details">•••</summary><div class="routine-popover"><small class="routine-identifier">Routine ${esc(r.id)}</small><p class="routine-sharing-note">${r.payload.family_followup ? "Family follow-up is allowed after " + r.payload.grace_minutes + " minutes without confirmation." : ntTr("Automatic family follow-up is off.")}</p></div></details><p>${esc(r.payload.local_time)} · ${esc(r.payload.timezone)} <span class="routine-state" data-state="${esc(r.status)}">${esc(r.status.replaceAll("_", " "))}</span></p><p class="muted">${esc(r.payload.start_date)} to ${esc(r.payload.end_date)}</p><button data-consent-routine="${r.id}">${r.status === "awaiting_consent" ? ntTr("Review proposed routine") : ntTr("Timing, sharing and pause controls")}</button>${S.editRoutine === r.id ? renderRoutineControls(r) : ""}</article>`).join("") || ntUi("<p>No recurring routine has been set.</p>")}</div><details><summary>Set a routine for an approved activity</summary><form id="newRoutine"><label>Approved activity<select name="template_id" required>${templates
    .filter((t) => !routines.some((r) => r.template_id === t.id))
    .map((t) => ntUi`<option value="${t.id}">${esc(t.payload.title)}</option>`)
    .join(
      "",
    )}</select></label>${scheduleFields()}<p class="muted">Quiet hours start at 21:00 and end at 07:00 by default. Automatic follow-up stays off until you choose a family contact.</p><button class="primary" ${templates.some((t) => !routines.some((r) => r.template_id === t.id)) ? "" : "disabled"}>Confirm routine</button></form></details></section>`;
}
function renderRoutineControls(r) {
  const family = S.contacts.filter((c) => c.role === "family");
  return ntUi`<form class="routine-consent" data-routine="${r.id}"><label class="check-label"><input name="active" type="checkbox" ${r.status === "active" ? "checked" : ""}> Run this routine</label><label class="check-label"><input name="family_followup" type="checkbox" ${r.payload.family_followup ? "checked" : ""}> Ask my chosen family contact to check in if this activity stays unconfirmed</label><label>Family contact<select name="recipient_id"><option value="">Choose a contact</option>${family.map((c) => ntUi`<option value="${esc(c.id)}" ${c.id === r.payload.recipient_id ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select></label><label>Wait this many minutes before follow-up<input type="number" name="grace_minutes" min="15" max="1440" value="${r.payload.grace_minutes}"></label><div class="schedule-dates"><label>Quiet hours start<input type="time" name="quiet_start" value="${r.payload.quiet_start}" required></label><label>Quiet hours end<input type="time" name="quiet_end" value="${r.payload.quiet_end}" required></label></div><p class="muted">Quiet hours use ${esc(r.payload.timezone)}. No emergency service is contacted. A missing response is not proof of a missed activity.</p><button class="primary">Confirm routine choices</button></form><details><summary>Change the time or date range</summary><form class="routine-schedule" data-routine="${r.id}">${scheduleFields(r.payload)}<button>Confirm timing change</button></form></details>`;
}
function renderNotificationSettings() {
  return ntUi`<section class="card"><h2>Device notifications</h2><p>In-app reminders work without browser permission. You can also request generic device alerts while this app is open and visible. No background push, SMS or emergency delivery is connected.</p><button id="enableRoutineNotifications">Enable notifications on this device</button><button id="disableRoutineNotifications">Turn device alerts off</button><p class="muted">${window.Notification ? "Browser permission: " + esc(Notification.permission) : ntTr("This browser does not support notifications.")} Device alerts contain no activity title or patient name.</p></section>`;
}
async function queueDatabase() {
  if (!window.indexedDB)
    throw Error("Offline saving is unavailable. Please reconnect before responding.");
  return new Promise((resolve, reject) => {
    const r = indexedDB.open("neurotwin-responses", 1);
    r.onupgradeneeded = () => r.result.createObjectStore("actions", { keyPath: "id" });
    r.onsuccess = () => resolve(r.result);
    r.onerror = () =>
      reject(
        Error("This browser cannot save an offline response. Please reconnect before responding."),
      );
  });
}
async function queueOperation(method, value) {
  const db = await queueDatabase();
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction("actions", method === "getAll" ? "readonly" : "readwrite"),
        store = tx.objectStore("actions");
      const req = store[method](value);
      let result;
      req.onsuccess = () => (result = req.result);
      tx.oncomplete = () => resolve(result);
      tx.onerror = () => reject(Error("The offline response could not be saved."));
    });
  } finally {
    db.close();
  }
}
async function loadOfflineActions() {
  try {
    S.offlineActions = (await queueOperation("getAll")).filter(
      (x) => x.user_id === S.user?.id && x.patient_id === S.pid,
    );
  } catch {
    S.offlineActions = [];
  }
}
async function clearOfflineActions(userId) {
  try {
    for (const x of await queueOperation("getAll"))
      if (x.user_id === userId) await queueOperation("delete", x.id);
  } catch {}
}
async function countOfflineActions(userId) {
  try {
    return (await queueOperation("getAll")).filter((packet) => packet.user_id === userId).length;
  } catch {
    return 0;
  }
}
async function submitRoutineResponse(oid, response, recipient = null) {
  const o = S.routineData.occurrences.find((o) => o.id === oid);
  if (!o || S.routineSending) return;
  await loadOfflineActions();
  if (S.offlineActions.some((x) => x.occurrence_id === oid)) {
    note(
      ntTr(
        "A response for this activity is already waiting on this device. Review it before adding another.",
      ),
    );
    return;
  }
  S.routineSending = true;
  const packet = {
    id: S.user.id + ":" + oid,
    user_id: S.user.id,
    patient_id: S.pid,
    occurrence_id: oid,
    created_at: new Date().toISOString(),
    body: {
      command_id: crypto.randomUUID(),
      task_version: o.task.version,
      routine_version: o.routine_version,
      response,
      recipient_id: recipient,
      snooze_minutes: 15,
    },
  };
  let committed = false;
  try {
    const saved = await api(
      `/patients/${S.pid}/routines/occurrences/${oid}/response`,
      "POST",
      packet.body,
    );
    committed = true;
    o.status = saved.status;
    o.reminder_at = saved.reminder_at;
    o.task.version = saved.task_version;
    o.task.status = response === "snooze" ? "deferred" : response;
    S.helpOccurrence = null;
    await refresh();
    note(ntTr("Your response was confirmed by the server."));
  } catch (e) {
    if (committed) {
      render();
      note(ntTr("Your response was saved. Reconnect to refresh the remaining details."));
      return;
    }
    if (e instanceof TypeError || !navigator.onLine || e.status >= 500) {
      await queueOperation("put", packet);
      await loadOfflineActions();
      render();
      note(ntTr("Saved on this device. It is not yet confirmed by the server."));
    } else throw e;
  } finally {
    S.routineSending = false;
  }
}
async function flushOfflineActions() {
  if (S.flushingOffline || !S.user || !navigator.onLine) return;
  S.flushingOffline = true;
  const actor = S.user.id,
    pid = S.pid;
  try {
    await loadOfflineActions();
    for (const packet of S.offlineActions) {
      if (packet.conflict || S.user?.id !== actor || S.pid !== pid) continue;
      if (Date.now() - new Date(packet.created_at).getTime() > 24 * 3600000) {
        packet.conflict = true;
        await queueOperation("put", packet);
        continue;
      }
      try {
        await api(
          `/patients/${pid}/routines/occurrences/${packet.occurrence_id}/response`,
          "POST",
          packet.body,
        );
        await queueOperation("delete", packet.id);
      } catch (e) {
        if ([400, 403, 404, 409, 422].includes(e.status)) {
          packet.conflict = true;
          await queueOperation("put", packet);
        } else break;
      }
    }
    await loadOfflineActions();
  } finally {
    S.flushingOffline = false;
  }
}
async function deviceId() {
  let id = localStorage.getItem("nt-reminder-device");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("nt-reminder-device", id);
  }
  return id;
}
async function enableRoutineNotifications() {
  if (!window.Notification || !navigator.serviceWorker || !window.isSecureContext) {
    note(ntTr("Device notifications are unavailable here. In-app reminders still work."));
    return;
  }
  const permission = await Notification.requestPermission();
  if (permission !== "granted" || Notification.permission !== "granted") {
    note(ntTr("Notifications were not enabled. In-app reminders still work."));
    return;
  }
  await navigator.serviceWorker.register("/mobile/notification-worker.js", { scope: "/mobile/" });
  await navigator.serviceWorker.ready;
  localStorage.setItem("nt-notify:" + S.user.id, "on");
  note(ntTr("Device alerts are enabled while this app is open."));
  await pollRoutineNotifications();
}
async function closeDeviceNotifications() {
  if (!navigator.serviceWorker) return;
  try {
    const reg = await navigator.serviceWorker.getRegistration("/mobile/");
    if (reg) for (const n of await reg.getNotifications()) n.close();
  } catch {}
}
async function pollRoutineNotifications() {
  if (!S.user || document.hidden || !window.Notification || Notification.permission !== "granted")
    return;
  try {
    if (localStorage.getItem("nt-notify:" + S.user.id) !== "on") return;
  } catch {
    return;
  }
  const actor = S.user.id,
    pid = S.pid,
    reg = await navigator.serviceWorker?.getRegistration("/mobile/");
  if (!reg) return;
  const activeTags = new Set(
    (S.routineData?.reminders || [])
      .filter((n) => n.state !== "acknowledged" && n.device_allowed)
      .map((n) => "nt-" + n.id + "-" + n.version),
  );
  for (const shown of await reg.getNotifications())
    if (shown.tag.startsWith("nt-") && !activeTags.has(shown.tag)) shown.close();
  const device = await deviceId();
  for (const n of S.routineData?.reminders || []) {
    if (!n.device_allowed || n.state !== "available_in_app") continue;
    const body = { expected_version: n.version, device_id: device };
    try {
      const claimed = await api(`/patients/${pid}/routines/reminders/${n.id}/device`, "POST", {
        ...body,
        state: "claim",
      });
      if (S.user?.id !== actor || S.pid !== pid) return;
      if (!claimed.claimed) continue;
      try {
        await reg.showNotification("NeuroTwin reminder", {
          body: ntTr("Open NeuroTwin to review an activity or a support request."),
          tag: "nt-" + n.id + "-" + n.version,
          data: { path: "/mobile/" },
          silent: true,
        });
        if (S.user?.id !== actor) {
          await closeDeviceNotifications();
          return;
        }
        await api(`/patients/${pid}/routines/reminders/${n.id}/device`, "POST", {
          ...body,
          state: "requested",
        });
      } catch {
        await api(`/patients/${pid}/routines/reminders/${n.id}/device`, "POST", {
          ...body,
          state: "failed",
        });
      }
    } catch {
      /* A revoked grant or stale reminder must not produce a device alert. */
    }
  }
}
function bindRoutines() {
  document
    .querySelectorAll("[data-routine-response]")
    .forEach(
      (b) =>
        (b.onclick = () =>
          guard(() => submitRoutineResponse(b.dataset.occurrence, b.dataset.routineResponse))),
    );
  document.querySelectorAll("[data-routine-help]").forEach(
    (b) =>
      (b.onclick = () => {
        S.helpOccurrence = b.dataset.routineHelp;
        render();
      }),
  );
  if ($("#routineHelp"))
    $("#routineHelp").onsubmit = (e) => {
      e.preventDefault();
      guard(() =>
        submitRoutineResponse(S.helpOccurrence, "help", new FormData(e.target).get("recipient_id")),
      );
    };
  if ($("#cancelRoutineHelp"))
    $("#cancelRoutineHelp").onclick = () => {
      S.helpOccurrence = null;
      render();
    };
  document.querySelectorAll("[data-ack-reminder]").forEach(
    (b) =>
      (b.onclick = () =>
        guard(async () => {
          const n = S.routineData.reminders.find((n) => n.id === b.dataset.ackReminder);
          await api(`/patients/${S.pid}/routines/reminders/${n.id}/acknowledge`, "POST", {
            expected_version: n.version,
            action: "acknowledge",
          });
          await refresh();
          note(ntTr("Reminder acknowledged. Activity completion has not changed."));
        })),
  );
  document.querySelectorAll("[data-consent-routine]").forEach(
    (b) =>
      (b.onclick = () => {
        S.editRoutine =
          S.editRoutine === b.dataset.consentRoutine ? null : b.dataset.consentRoutine;
        render();
      }),
  );
  if ($("#newRoutine"))
    $("#newRoutine").onsubmit = (e) => {
      e.preventDefault();
      const f = new FormData(e.target),
        task = records("task").find((t) => t.id === f.get("template_id"));
      guard(async () => {
        await api(`/patients/${S.pid}/routines`, "POST", {
          ...scheduleBody(e.target),
          template_id: task.id,
          template_version: task.version,
        });
        await refresh();
        note(ntTr("Routine confirmed. The server worker will create dated activities."));
      });
    };
  document.querySelectorAll(".routine-consent").forEach(
    (form) =>
      (form.onsubmit = (e) => {
        e.preventDefault();
        const r = S.routineData.routines.find((r) => r.id === form.dataset.routine),
          f = new FormData(form);
        guard(async () => {
          await api(`/patients/${S.pid}/routines/${r.id}/consent`, "POST", {
            expected_version: r.version,
            active: f.has("active"),
            family_followup: f.has("family_followup"),
            recipient_id: f.get("recipient_id") || null,
            grace_minutes: Number(f.get("grace_minutes")),
            quiet_start: f.get("quiet_start"),
            quiet_end: f.get("quiet_end"),
          });
          await refresh();
          note(ntTr("Your routine and follow-up choices were saved."));
        });
      }),
  );
  document.querySelectorAll(".routine-schedule").forEach(
    (form) =>
      (form.onsubmit = (e) => {
        e.preventDefault();
        const r = S.routineData.routines.find((r) => r.id === form.dataset.routine);
        guard(async () => {
          await api(`/patients/${S.pid}/routines/${r.id}/schedule`, "POST", {
            ...scheduleBody(form),
            expected_version: r.version,
          });
          await refresh();
          note(ntTr("Routine timing updated. Old pending reminders were cancelled."));
        });
      }),
  );
  document.querySelectorAll("[data-discard-offline]").forEach(
    (b) =>
      (b.onclick = () =>
        guard(async () => {
          await queueOperation("delete", b.dataset.discardOffline);
          await loadOfflineActions();
          render();
        })),
  );
  if ($("#enableRoutineNotifications"))
    $("#enableRoutineNotifications").onclick = () => guard(enableRoutineNotifications);
  if ($("#disableRoutineNotifications"))
    $("#disableRoutineNotifications").onclick = () =>
      guard(async () => {
        localStorage.removeItem("nt-notify:" + S.user.id);
        await closeDeviceNotifications();
        note(ntTr("Device alerts turned off for this account."));
      });
}
let routinesPolling = false;
setInterval(async () => {
  if (
    !S.user ||
    !S.pid ||
    !S.data ||
    S.workspaceChanging ||
    routinesPolling ||
    document.hidden ||
    S.busy ||
    S.recording
  )
    return;
  routinesPolling = true;
  try {
    await flushOfflineActions();
    const old =
      JSON.stringify(S.routineData?.routines) +
      JSON.stringify(S.routineData?.occurrences) +
      JSON.stringify(S.routineData?.reminders);
    if (!(await updateRoutineData())) return;
    const data = S.routineData;
    const changed =
      old !==
      JSON.stringify(data.routines) +
        JSON.stringify(data.occurrences) +
        JSON.stringify(data.reminders);
    if (
      changed &&
      !S.assessmentActive &&
      !S.assessmentBusy &&
      !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)
    )
      render();
    await pollRoutineNotifications();
  } catch {
    /* Keep queued responses pending until access and connectivity are restored. */
  } finally {
    routinesPolling = false;
  }
}, 10000);
window.addEventListener("online", () => {
  if (S.user)
    guard(async () => {
      await flushOfflineActions();
      if (!S.assessmentActive && !S.assessmentBusy) await refresh();
    });
});
