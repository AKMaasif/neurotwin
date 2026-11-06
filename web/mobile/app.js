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
  if (expectedActor && S.user?.id !== expectedActor)
    throw new Error("Session changed; stale response discarded");
  if (!r.ok) {
    const e = await r.json().catch(() => ({}));
    if (
      typeof e.detail === "string" &&
      (e.detail.startsWith("Session account changed") || e.detail === "Invalid CSRF token")
    )
      careSessionChanged();
    const error = new Error(typeof e.detail === "string" ? e.detail : "Request unavailable");
    error.status = r.status;
    throw error;
  }
  const result = await r.json();
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
  S.data = await api(`/patients/${S.pid}/workspace`);
  await updateRoutineData();
  await loadOfflineActions();
  S.contacts = S.data.scopes.includes("help")
    ? await api(`/patients/${S.pid}/companion/contacts`)
    : [];
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
  document.documentElement.classList.toggle("large", pref?.payload.text_size === "large");
  if (S.tab === "weekly") await loadWeeklyReports();
  if (S.tab === "messages") await loadCareMessages();
  render();
}
function icon(k) {
  const paths = {
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
  document.body.classList.toggle("care-chat-page", careActive());
  pauseCareAudio();
  const family = S.user.role === "family";
  const tasks = records("task").filter(
    (t) => t.status !== "superseded" && !t.payload.is_routine_template && !t.payload.occurrence_id,
  );
  const plan = records("plan").find((p) => p.status === "approved");
  let body = "";
  if (S.tab === "home") {
    body = `<h1>${family ? "Care circle overview" : "Hello, " + esc(S.memory?.enabled && S.memory.preferred_name ? S.memory.preferred_name : S.user.name)}</h1><p>${esc(new Intl.DateTimeFormat("en", { dateStyle: "full" }).format(new Date()))}</p>${renderDailyActivities()}${family ? `<section class="card"><h2>Shared support</h2><p>Task responses are participant reports. No clinical stability estimate is available.</p><button data-tab="support">Open help requests</button></section>` : tasks[0] ? taskCard(tasks.find((t) => t.status === "pending") || tasks[0], true) : S.routineData?.occurrences.some(activeOccurrence) ? "" : '<section class="card">No active task. Your care team can review your plan.</section>'}<section class="card"><h2>Your current plan</h2><p>${esc(plan?.payload.source_review_required ? "Your plan is waiting for care-team review." : plan?.payload.instructions || "No approved plan available.")}</p><p class="muted">Synthetic support plan · ${esc(plan?.payload.signed_by || "Not signed")}</p>${plan?.payload.source_review_required ? '<p class="error">A source was corrected. Your care team needs to review this plan. Please ask for help before acting on affected instructions.</p>' : ""}</section><section class="card"><h2>One thing at a time</h2><div class="actions"><button data-tab="plan">My plan</button><button data-tab="support">Ask for help</button></div></section>`;
  }
  if (S.tab === "home")
    body +=
      '<section class="card"><h2>This week</h2><p>Review recorded activities and reports shared by your care team.</p><button data-tab="weekly">Weekly summary</button></section>';
  if (S.data.scopes.includes("messages") && S.tab === "home")
    body +=
      '<section class="card"><h2>Your care circle</h2><p>Talk with your family or care team.</p><button data-tab="messages">Messages</button></section>';
  if (S.tab === "messages") body = renderCareMessages();
  if (S.tab === "weekly") body = renderWeeklyReports();
  if (S.tab === "plan")
    body = `<h1>${family ? "Shared tasks" : "My plan"}</h1><p>Follow the current approved instructions. Ask for help when you need it.</p>${tasks.map((t) => taskCard(t)).join("")}${renderDailyActivities()}${renderRoutineManager()}`;
  if (S.tab === "check")
    body = `<h1>My check</h1><section class="card"><h2>No assessment assigned</h2><p>Research measurements need an approved protocol and suitable device capture. This build does not diagnose cognitive impairment.</p><button data-tab="support">Report a concern</button></section>`;
  if (S.tab === "companion") body = renderCompanion();
  if (S.tab === "support")
    body = `<h1>Support</h1><section class="card"><h2>Ask for practical help</h2><p>No emergency service is monitored or contacted by this app.</p><form id="help"><label>Recipient<select name="recipient_id">${S.contacts.map((c) => `<option value="${esc(c.id)}">${esc(c.name)} · ${esc(c.role)}</option>`).join("")}</select></label><label>Your request<textarea name="text" maxlength="1000" required>${esc(S.helpDraft || "Please help me prepare transport for my appointment.")}</textarea></label><button class="primary" ${S.contacts.length ? "" : "disabled"}>Confirm and save request</button></form></section>${records(
      "help",
    )
      .map(
        (h) =>
          `<section class="card"><h2>${esc(h.status === "closed_unconfirmed" ? "Closed without activity confirmation" : h.status.replaceAll("_", " "))}</h2><p>${esc(h.payload.text)}</p>${h.payload.recipient_id === S.user.id && h.status === "requested" ? `<button data-accept="${h.id}">Accept responsibility</button>` : ""}<p class="muted">Saved in app. Push/SMS is not connected.</p></section>`,
      )
      .join(
        "",
      )}<section class="card"><h2>Tell your care team</h2><form id="concern"><label>Your concern<textarea name="text" maxlength="1500" required></textarea></label><label><input type="checkbox" name="urgent" style="width:auto"> I am reporting a sudden concerning change</label><button>Save for review</button></form><p class="muted">For urgent help, do not wait for an app reply. Use your locally approved assistance route.</p></section>`;
  if (S.tab === "support" && S.data.scopes.includes("messages"))
    body = body.replace(
      "<h1>Support</h1>",
      '<h1>Support</h1><section class="card"><h2>Your conversations</h2><button data-tab="messages">Messages</button></section>',
    );
  if (S.tab === "settings")
    body = `<h1>Settings</h1><section class="card"><h2>Reading comfort</h2><button id="size">${document.documentElement.classList.contains("large") ? "Use normal text" : "Use larger text"}</button><button id="contrast">Toggle contrast</button></section>${renderMemorySettings()}${renderNotificationSettings()}<section class="card"><h2>Your session</h2><p>Signed in as ${esc(S.user.name)}. Family access requires its own account.</p><button id="logout">Sign out</button></section>`;
  $("#app").innerHTML =
    `<header><strong>NeuroCompanion</strong><button class="plain" data-tab="settings">Settings</button></header><div class="scope">${esc(S.data.patient.name)} · ${esc(family ? "Authorized relative" : "Participant")}<br><span class="muted">Synthetic development workspace · ${navigator.onLine ? "Server-connected" : "Offline"}</span></div><main>${body}</main><nav aria-label="Main navigation">${[
      ["home", "Home"],
      ["check", "My Check"],
      ["companion", "Companion"],
      ["plan", "My Plan"],
      ["support", "Support"],
    ]
      .map(
        ([key, label]) =>
          `<button data-tab="${key}" class="${S.tab === key ? "active" : ""}" aria-current="${S.tab === key ? "page" : "false"}">${icon(key)}${label}</button>`,
      )
      .join("")}</nav>`;
  bind();
}
function bind() {
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
        await api(`/patients/${S.pid}/preferences`, "POST", {
          text_size: document.documentElement.classList.contains("large") ? "normal" : "large",
        });
        await refresh();
      });
  if ($("#contrast"))
    $("#contrast").onclick = () => document.body.classList.toggle("high-contrast");
  if ($("#logout"))
    $("#logout").onclick = () =>
      guard(async () => {
        await loadOfflineActions();
        if (
          S.offlineActions.length &&
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
        resetCareMessages();
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
  S.tab = "home";
  resetCareMessages();
  S.reportNotes = {};
  S.weekly = null;
  S.reportHistory = [];
  S.reportId = null;
  S.reportEnd = null;
  S.reportZone = "Asia/Dubai";
  S.dirty = false;
  S.reportEpoch = (S.reportEpoch || 0) + 1;
  S.memory = null;
  S.chat = [];
  S.pendingAction = null;
  S.guide = null;
  S.draftText = "";
  S.helpDraft = "";
  const ps = await api("/patients");
  S.pid = ps[0]?.id;
  if (!S.pid) throw new Error("No active workspace grant");
  await refresh();
  if (S.user.role === "participant" && S.data.scopes.includes("preferences")) {
    S.memory = await api(`/patients/${S.pid}/companion/memory`);
    S.chat = S.memory.history.flatMap((h) => [
      { role: "user", text: h.user },
      { role: "bot", text: h.assistant },
    ]);
    render();
  }
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
