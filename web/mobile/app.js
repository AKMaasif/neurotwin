const S = {
  user: null,
  csrf: "",
  pid: null,
  data: null,
  tab: "home",
  chat: [],
  recording: false,
  busy: false,
  voiceState: "idle",
  voiceEpoch: 0,
  draftText: "",
  contacts: [],
  memory: null,
};
const $ = (s) => document.querySelector(s);
const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
async function api(path, method = "GET", body, signal) {
  const expectedActor = S.user?.id;
  const expectedWorkspace = S.workspaceEpoch;
  const patientRequest = path.startsWith("/patients/");
  const r = await fetch("/api" + path, {
    method,
    signal,
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      "X-CSRF-Token": S.csrf,
      ...(S.user ? { "X-Expected-Actor": S.user.id } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (patientRequest && expectedWorkspace !== S.workspaceEpoch)
    throw new Error("Workspace changed; stale response discarded");
  if (expectedActor && S.user?.id !== expectedActor)
    throw new Error("Session changed; stale response discarded");
  if (!r.ok) {
    const e = await r.json().catch(() => ({}));
    if (r.status === 401 && expectedActor)
      careSessionChanged("Your session expired or was signed out. Sign in again.");
    else if (
      typeof e.detail === "string" &&
      (e.detail.startsWith("Session account changed") || e.detail === "Invalid CSRF token")
    )
      careSessionChanged();
    const error = new Error(typeof e.detail === "string" ? e.detail : "Request unavailable");
    error.status = r.status;
    throw error;
  }
  const result = await r.json();
  if (patientRequest && expectedWorkspace !== S.workspaceEpoch)
    throw new Error("Workspace changed; stale response discarded");
  if (expectedActor && S.user?.id !== expectedActor)
    throw new Error("Session changed; stale response discarded");
  if (["/login", "/logout"].includes(path)) announceCareSessionChange();
  return result;
}
function note(t) {
  $("#notice").textContent = t;
  $("#notice").style.display = "block";
  clearTimeout(note.timer);
  note.timer = setTimeout(() => ($("#notice").style.display = "none"), 6000);
}
function records(kind) {
  return S.data.records.filter((r) => r.kind === kind);
}
async function refresh() {
  const pid = S.pid,
    epoch = S.workspaceEpoch;
  const data = await fetchAuthorizedWorkspace(pid);
  if (!data) return;
  const [routineData, contacts, sharingAccess] = await Promise.all([
    api(`/patients/${pid}/routines`),
    data.scopes.includes("help") ? api(`/patients/${pid}/companion/contacts`) : Promise.resolve([]),
    S.user.role === "participant" && data.scopes.includes("sharing")
      ? api(`/patients/${pid}/grants`)
      : Promise.resolve([]),
  ]);
  if (S.pid !== pid || S.workspaceEpoch !== epoch) return;
  S.data = data;
  S.routineData = routineData;
  S.contacts = contacts;
  S.sharingAccess = sharingAccess;
  await loadOfflineActions();
  if (S.pid !== pid || S.workspaceEpoch !== epoch) return;
  for (const key of ["guide", "pendingAction"]) {
    const task = S[key]?.task;
    if (
      task &&
      !records("task").some(
        (t) =>
          t.id === task.id &&
          t.version === task.version &&
          !records("plan").find((p) => p.id === t.payload.plan_id)?.payload.source_review_required,
      )
    )
      S[key] = null;
  }
  const pref = records("preference")[0];
  document.documentElement.classList.toggle(
    "large",
    S.user.role === "participant" ? pref?.payload.text_size === "large" : !!S.accountTextLarge,
  );
  if (S.tab === "weekly") await loadWeeklyReports();
  if (S.tab === "messages") await loadCareMessages();
  render();
}
function icon(k) {
  const paths = {
    messages: "M4 4h16v13H9l-5 4z M8 8h8m-8 4h6",
    weekly: "M5 3h14v18H5z M8 8h8m-8 5h8m-8 5h5",
    settings:
      "M12 3v3m0 12v3M3 12h3m12 0h3M6 6l2 2m8 8 2 2M6 18l2-2m8-8 2-2 M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
    home: "M3 10 12 3l9 7v11H3z M9 21v-8h6v8",
    check: "M9 3h6v3h5v15H4V6h5z M8 13l3 3 5-6",
    companion: "M5 5h14v12H9l-4 4z M8 10h1m6 0h1",
    plan: "M5 3h14v18H5z M8 8h8m-8 5h8m-8 5h5",
    support: "M8 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M2 21v-3a6 6 0 0 1 12 0v3m4-12v8m-4-4h8",
  };
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="${paths[k] || paths.home}"/></svg>`;
}
function login() {
  $("#app").innerHTML =
    `<main class="login"><div class="eyebrow">NEUROTWIN</div><h1>A little support for your day</h1><p>Sign in to your own workspace.</p><form id="login"><label>Account<select name="username"><option value="participant">Participant (synthetic)</option><option value="family">Family (synthetic)</option></select></label><label>Password<input name="password" type="password" autocomplete="current-password" required></label><button class="primary">Sign in</button><p class="muted">Local development accounts. Password is stored in the server .env file.</p><p id="error" role="alert"></p></form></main>`;
  $("#login").onsubmit = async (e) => {
    e.preventDefault();
    try {
      const f = new FormData(e.target);
      S.user = await api("/login", "POST", Object.fromEntries(f));
      S.csrf = S.user.csrf;
      await start();
    } catch (x) {
      $("#error").textContent = x.message;
    }
  };
}
function taskCard(t, hero = false) {
  const reviewHold = records("plan").some(
    (p) => p.id === t.payload.plan_id && p.payload.source_review_required,
  );
  return `<section class="card ${hero ? "hero" : ""}"><div class="eyebrow">${esc(t.payload.period)} · ${esc(t.payload.time)}</div><h2>${esc(t.payload.title)}</h2><p class="muted">${t.status === "completed" ? "Confirmed by participant" : esc(t.status === "pending" ? "Not yet confirmed" : t.status)}</p><div class="actions">${reviewHold ? '<p class="error">This task is waiting for source review. Please ask your care team for help.</p>' : ""}${S.data.scopes.includes("respond") && !reviewHold ? `<button class="primary" data-response="completed" data-id="${t.id}">Done</button><button data-response="deferred" data-id="${t.id}">Later</button>` : ""}<button data-coach="${t.id}">Step guide</button></div></section>`;
}
function render() {
  if (!S.user || !S.data) return;
  clearCameraAssistance();
  document.body.classList.toggle("care-chat-page", careActive());
  pauseCareAudio();
  document.body.dataset.mobilePage = S.tab;
  const family = S.user.role === "family";
  const tasks = records("task").filter(
    (t) => t.status !== "superseded" && !t.payload.is_routine_template && !t.payload.occurrence_id,
  );
  const plan = records("plan").find((p) => p.status === "approved");
  let body = "";
  if (S.tab === "home") body = `<div class="adaptive-home">${renderMobileHome(tasks, plan)}</div>`;
  if (S.tab === "messages") body = renderCareMessages();
  if (S.tab === "weekly") body = `<div class="mobile-report-page">${renderWeeklyReports()}</div>`;
  if (S.tab === "plan") body = renderMobilePlan(tasks, plan);
  if (S.tab === "check") body = renderMobileCheck();
  if (S.tab === "companion") body = `<div class="adaptive-companion">${renderCompanion()}</div>`;
  if (S.tab === "support") body = renderMobileSupport();
  if (S.tab === "settings") body = renderMobileSettings();
  const followLatest =
    careActive() &&
    !S.care?.before &&
    (S.care?.forceLatest || !S.care?.scroll || S.care.scroll.bottom);
  $("#app").innerHTML =
    `<a class="skip-link" href="#mobile-content">Skip to content</a><div class="adaptive-shell"><aside class="adaptive-navigation"><div class="adaptive-brand"><span class="brand-mark" aria-hidden="true">${brandMark()}</span><strong>NeuroCompanion</strong><button id="nav-density" class="plain" aria-label="Toggle compact navigation" aria-expanded="${!document.documentElement.classList.contains("nav-compact")}">↔</button></div><div class="adaptive-nav-slot"></div><div class="adaptive-nav-context"><span class="patient-initial" aria-hidden="true">${esc(S.data.patient.name.slice(0, 1))}</span><strong>${esc(S.data.patient.name)}</strong><small>${esc(family ? "Authorized relative" : "Participant")} workspace</small><button data-tab="settings" aria-current="${S.tab === "settings" ? "page" : "false"}">${icon("settings")}<span>Settings</span></button></div></aside><div class="adaptive-workspace"><div class="adaptive-topbar"><header class="mobile-header"><div class="mobile-brand"><span class="brand-mark" aria-hidden="true">${brandMark()}</span><strong>NeuroCompanion</strong></div>${family ? `<button class="plain family-companion" data-tab="companion" aria-label="Companion">${icon("companion")}</button>` : ""}<button class="reference-reminders plain" data-tab="plan" aria-label="View reminders"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M5 16h14l-2-3V9a5 5 0 0 0-10 0v4l-2 3ZM9 20h6"/></svg>${S.routineData?.reminders.some((item) => item.state !== "acknowledged") ? '<span class="reminder-dot"></span>' : ""}</button><button class="plain reference-profile" data-tab="settings" aria-label="Settings"><span>${esc(S.user.name.slice(0, 1))}</span></button></header>${renderWorkspacePicker()}<div class="scope"><span class="patient-initial" aria-hidden="true">${esc(S.data.patient.name.slice(0, 1))}</span><span><strong>${esc(S.data.patient.name)}</strong><small>${esc(family ? "Authorized relative" : "Participant")} · Synthetic development workspace</small></span>${!navigator.onLine ? '<span class="offline-label" role="status">Offline</span>' : ""}</div></div><main id="mobile-content" class="adaptive-content" tabindex="-1">${body}</main><nav aria-label="Main navigation">${mobileNavigation(
      family,
    )
      .map(
        ([key, label]) =>
          `<button data-tab="${key}" aria-label="${label}" title="${label}" class="${S.tab === key ? "active" : ""}" aria-current="${S.tab === key ? "page" : "false"}">${icon(key)}<span>${label}</span></button>`,
      )
      .join("")}</nav></div></div>`;
  document
    .querySelector(".adaptive-nav-slot")
    .append(document.querySelector('nav[aria-label="Main navigation"]'));
  syncMobileDock();
  bind();
  syncMobileHistory(followLatest);
}
function bind() {
  bindPlanFilters();
  bindRoutineFilters();
  if ($("#nav-density"))
    $("#nav-density").onclick = () => {
      const compact = document.documentElement.classList.toggle("nav-compact");
      $("#nav-density").setAttribute("aria-expanded", String(!compact));
    };
  document.querySelectorAll("[data-revoke-access]").forEach(
    (button) =>
      (button.onclick = () =>
        guard(async () => {
          const person = S.sharingAccess?.find(
            (item) => item.actor_id === button.dataset.revokeAccess,
          );
          if (
            !person ||
            !confirm(
              `Remove ${person.name}'s access to this patient? Future app access will stop. Previously downloaded information cannot be recalled.`,
            )
          )
            return;
          await api(
            `/patients/${S.pid}/grants/${encodeURIComponent(person.actor_id)}/revoke`,
            "POST",
          );
          await refresh();
          note("Access removed. Previously downloaded information is not recalled.");
        })),
  );

  bindWorkspacePicker();
  bindResearchSessions();
  bindAccountSessions();
  bindIotSimulation();
  bindCameraAssistance();
  bindCareMessages();
  bindWeeklyReports();
  document.querySelectorAll("[data-tab]").forEach(
    (b) =>
      (b.onclick = () => {
        if (S.dirty && !confirm("Discard unsaved report edits?")) return;
        S.dirty = false;
        stopCompanion(false);
        stopCareCapture();
        S.tab = b.dataset.tab;
        if (S.tab === "companion") setVoiceState("idle");
        render();
        if (S.tab === "weekly")
          guard(async () => {
            await loadWeeklyReports();
            if (S.tab === "weekly") render();
          });
        if (S.tab === "messages")
          guard(async () => {
            await loadCareMessages();
            if (S.tab === "messages") render();
          });
        window.scrollTo(0, 0);
      }),
  );
  document.querySelectorAll("[data-response]").forEach(
    (b) =>
      (b.onclick = () =>
        guard(async () => {
          const t = records("task").find((t) => t.id === b.dataset.id);
          await api(`/patients/${S.pid}/tasks/${t.id}/response`, "POST", {
            command_id: crypto.randomUUID(),
            expected_version: t.version,
            response: b.dataset.response,
          });
          await refresh();
          note("Your response was saved.");
        })),
  );
  document.querySelectorAll("[data-coach]").forEach(
    (b) =>
      (b.onclick = () => {
        const t = records("task").find((t) => t.id === b.dataset.coach);
        S.tab = "companion";
        send("guide my activity", { id: t.id, version: t.version });
      }),
  );
  document.querySelectorAll("[data-accept]").forEach(
    (b) =>
      (b.onclick = () =>
        guard(async () => {
          const h = records("help").find((h) => h.id === b.dataset.accept);
          await api(`/patients/${S.pid}/help/${h.id}/accept`, "POST", {
            command_id: crypto.randomUUID(),
            expected_version: h.version,
          });
          await refresh();
          note("Responsibility accepted.");
        })),
  );
  if ($("#help"))
    $("#help").onsubmit = (e) => {
      e.preventDefault();
      const body = Object.fromEntries(new FormData(e.target));
      guard(async () => {
        await api(`/patients/${S.pid}/help`, "POST", { ...body, command_id: crypto.randomUUID() });
        await refresh();
        note("Help request saved in app.");
      });
    };
  if ($("#concern"))
    $("#concern").onsubmit = (e) => {
      e.preventDefault();
      const f = new FormData(e.target);
      guard(async () => {
        await api(`/patients/${S.pid}/concerns`, "POST", {
          command_id: crypto.randomUUID(),
          text: f.get("text"),
          urgent_reported: f.has("urgent"),
        });
        await refresh();
        note(
          f.has("urgent")
            ? "Concern recorded. Do not wait for this app for urgent assistance."
            : "Concern saved for clinician review.",
        );
      });
    };
  if ($("#size"))
    $("#size").onclick = () =>
      guard(async () => {
        if (!S.data.scopes.includes("preferences")) {
          S.accountTextLarge = !document.documentElement.classList.contains("large");
          document.documentElement.classList.toggle("large", S.accountTextLarge);
          const button = $("#size");
          button.textContent = S.accountTextLarge ? "Use normal text" : "Use larger text";
          button.setAttribute("aria-pressed", String(S.accountTextLarge));
          note("Text size changed for this open app.");
          return;
        }
        await api(`/patients/${S.pid}/preferences`, "POST", {
          text_size: document.documentElement.classList.contains("large") ? "normal" : "large",
        });
        await refresh();
      });
  if ($("#contrast"))
    $("#contrast").onclick = (event) => {
      const enabled = document.body.classList.toggle("high-contrast");
      event.currentTarget.setAttribute("aria-pressed", String(enabled));
    };
  if ($("#logout"))
    $("#logout").onclick = () =>
      guard(async () => {
        await loadOfflineActions();
        if (
          (await countOfflineActions(S.user.id)) > 0 &&
          !confirm("Signing out will discard unsent responses on this device. Continue?")
        )
          return;
        if (
          hasCareDrafts() &&
          !confirm(
            "Discard unsent message drafts? A request with an unconfirmed response may already be saved in the conversation.",
          )
        )
          return;
        stopCompanion(false);
        await clearOfflineActions(S.user.id);
        await closeDeviceNotifications();
        await api("/logout", "POST");
        clearPatientContext();
        S.workspaces = [];
        S.user = null;
        S.weekly = null;
        S.reportHistory = [];
        S.reportId = null;
        S.reportEpoch = (S.reportEpoch || 0) + 1;
        S.data = null;
        S.chat = [];
        S.memory = null;
        S.pendingAction = null;
        S.guide = null;
        S.draftText = "";
        S.helpDraft = "";
        S.contacts = [];
        login();
      });
  bindCompanion();
  bindRoutines();
}
async function guard(fn) {
  try {
    await fn();
  } catch (e) {
    note(e.message);
  }
}
async function start() {
  clearPatientContext();
  S.accountTextLarge = false;
  S.workspaceChanging = false;
  S.workspaces = await api("/patients");
  if (S.workspaces.length === 1) await activateWorkspace(S.workspaces[0].id, true);
  else workspaceState();
}

(async () => {
  try {
    S.user = await api("/session");
    S.csrf = S.user.csrf;
    if (S.user.role === "clinician") {
      location.href = "/dashboard/";
      return;
    }
    await start();
  } catch {
    login();
  }
})();

let revision = null,
  syncing = false;
setInterval(async () => {
  if (
    !S.user ||
    !S.pid ||
    S.workspaceChanging ||
    !S.data ||
    syncing ||
    S.busy ||
    S.reportBusy ||
    S.care?.busy ||
    careVoiceBusy() ||
    careAudioPlaying() ||
    S.dirty ||
    S.recording ||
    S.voiceState === "speaking" ||
    document.hidden ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)
  )
    return;
  syncing = true;
  try {
    const d = await api(`/patients/${S.pid}/changes`);
    if (revision && revision !== d.revision) await refresh();
    revision = d.revision;
  } catch (e) {
    if (e.message === "Sign in required" || e.message === "Access not granted") {
      stopCompanion(false);
      await clearOfflineActions(S.user.id);
      await closeDeviceNotifications();
      S.routineData = null;
      S.offlineActions = [];
      S.data = null;
      resetCareMessages();
      S.user = null;
      S.reportNotes = {};
      S.weekly = null;
      S.reportHistory = [];
      S.reportId = null;
      S.reportEpoch = (S.reportEpoch || 0) + 1;
      S.chat = [];
      S.memory = null;
      S.draftText = "";
      S.pendingAction = null;
      S.guide = null;
      login();
      note("Access expired or changed. Sign in again.");
    }
  } finally {
    syncing = false;
  }
}, 5000);
