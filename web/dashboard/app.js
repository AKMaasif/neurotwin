const S = { user: null, csrf: "", data: null, pid: null, tab: "overview", report: null };
const $ = (s) => document.querySelector(s);
const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
async function api(path, method = "GET", body) {
  const expectedActor = S.user?.id;
  const expectedWorkspace = S.workspaceEpoch;
  const patientRequest = path.startsWith("/patients/");
  const r = await fetch("/api" + path, {
    method,
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      "X-CSRF-Token": S.csrf,
      ...(S.user ? { "X-Expected-Actor": S.user.id } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const d = await r.json().catch(() => ({}));
  if (patientRequest && expectedWorkspace !== S.workspaceEpoch)
    throw new Error("Workspace changed; stale response discarded");
  if (expectedActor && S.user?.id !== expectedActor)
    throw new Error("Session changed; stale response discarded");
  if (!r.ok) {
    if (
      typeof d.detail === "string" &&
      (d.detail.startsWith("Session account changed") || d.detail === "Invalid CSRF token")
    )
      careSessionChanged();
    const error = new Error(typeof d.detail === "string" ? d.detail : "Request failed");
    error.status = r.status;
    throw error;
  }
  if (["/login", "/logout"].includes(path)) announceCareSessionChange();
  return d;
}
function note(t) {
  $("#notice").textContent = t;
  $("#notice").style.display = "block";
  clearTimeout(note.timer);
  note.timer = setTimeout(() => ($("#notice").style.display = "none"), 6000);
}
async function guard(fn) {
  try {
    await fn();
  } catch (e) {
    note(e.message);
  }
}
const rows = (k) => S.data.records.filter((r) => r.kind === k);
async function refresh() {
  const pid = S.pid,
    epoch = S.workspaceEpoch;
  const data = await fetchAuthorizedWorkspace(pid);
  if (!data) return;
  const [report, routineData, documents] = await Promise.all([
    api(`/patients/${pid}/report`),
    api(`/patients/${pid}/routines`),
    data.scopes.includes("review") ? api(`/patients/${pid}/documents`) : Promise.resolve([]),
  ]);
  if (S.pid !== pid || S.workspaceEpoch !== epoch) return;
  S.data = data;
  S.report = report;
  S.routineData = routineData;
  S.documents = documents;
  if (S.tab === "sources" && data.scopes.includes("review")) {
    if (!S.documents.some((d) => d.id === S.documentId)) S.documentId = S.documents[0]?.id;
    S.documentDetails = S.documentId
      ? await api(`/patients/${pid}/documents/${S.documentId}/details`)
      : null;
  }
  if (S.tab === "report") await loadWeeklyReports();
  if (S.tab === "messages") await loadCareMessages();
  if (S.pid === pid && S.workspaceEpoch === epoch) render();
}

function login() {
  $("#app").innerHTML =
    `<div class="login"><div class="eyebrow">NEUROTWIN CLINICAL</div><h1>Your review workspace</h1><p>Sign in with an assigned professional account.</p><form id="login"><label>Account<input name="username" value="clinician" autocomplete="username" required></label><label>Password<input name="password" type="password" autocomplete="current-password" required></label><button class="primary">Sign in</button><p class="muted">Synthetic local development. Password is in the server .env file.</p><p id="error" role="alert"></p></form></div>`;
  $("#login").onsubmit = (e) => {
    e.preventDefault();
    guard(async () => {
      S.user = await api("/login", "POST", Object.fromEntries(new FormData(e.target)));
      S.csrf = S.user.csrf;
      await start();
    });
  };
}
function render() {
  if (!S.user || !S.data) return;
  document.body.classList.toggle("care-chat-page", careActive());
  pauseCareAudio();
  if (!clinicalTabAllowed(S.tab)) S.tab = "overview";
  let content = "";
  const cases = rows("case");
  if (S.tab === "overview") content = renderClinicalOverview();
  if (S.tab === "queue") content = renderClinicalQueue();
  if (S.tab === "patient") content = renderClinicalPatient();
  if (S.tab === "sources") content = renderSourcePage();
  if (S.tab === "routines") content = renderClinicalRoutines();
  if (S.tab === "support")
    content = `<h1>Family support requests</h1><p>Granted contacts and actual in-app ownership states.</p>${
      rows("help")
        .map(
          (h) =>
            `<section class="card"><span class="badge">${esc(h.status)}</span><h2>${esc(h.payload.text)}</h2><p>From ${esc(h.payload.sender_id)} to ${esc(h.payload.recipient_id)}</p><p class="muted">In-app record saved. External messaging unavailable.</p></section>`,
        )
        .join("") || '<section class="card">No help requests.</section>'
    }`;
  if (S.tab === "messages") content = renderCareMessages();
  if (S.tab === "report") content = renderWeeklyReports();
  if (S.tab === "providers")
    content = `<h1>Model connections</h1><section class="card"><h2>Verify account catalog</h2><p>Lists accessible models without running inference. Keys remain on the server.</p><button id="catalog">Check configured providers</button><pre id="catalogResult" class="source"></pre></section><section class="card"><h2>Routing boundaries</h2><p>Gemini Flash: structured app requests. Muse Spark standard: bounded drafting adapter. Pro: selected review tasks. Numerical results and permissions remain deterministic. No live provider inference has been certified by this interface.</p></section>`;
  if (S.tab === "audit")
    content = `<h1>Access and action audit</h1><section class="card"><button id="loadAudit">Load current audit</button><div id="auditRows"></div></section>`;
  if (S.tab === "case") content = renderClinicalCase();
  if (S.tab === "case" && cases.some((c) => c.id === S.caseId && !c.payload.urgent_reported))
    content += renderEvidenceDrafts(S.caseId);
  $("#app").innerHTML =
    `<a class="skip-link" href="#clinical-content">Skip to content</a><aside id="clinical-navigation" class="sidebar ${S.navOpen ? "nav-open" : ""}"><div class="brand">NeuroTwin<div class="eyebrow">CLINICAL MONITORING</div></div><span class="eyebrow">MONITOR</span>${[
      ["overview", "Overview"],
      ["queue", "Work queue"],
      ["patient", "Patient workspace"],
      ["sources", "Source verification"],
      ["routines", "Daily routines"],
      ["support", "Family support"],
      ["messages", "Care messages"],
      ["report", "Activity report"],
      ["providers", "Model connections"],
      ["audit", "Audit"],
    ]
      .filter(([key]) => clinicalTabAllowed(key))
      .map(
        ([k, n]) =>
          `<button data-tab="${k}" class="${S.tab === k ? "active" : ""}" aria-current="${S.tab === k ? "page" : "false"}">${n}</button>`,
      )
      .join(
        "",
      )}<div class="bottom"><p><strong>${esc(S.user.name)}</strong><br>Assigned clinician</p><button id="dark">Dark mode</button><button id="logout">Sign out</button></div></aside><div class="main"><header class="topbar"><button id="workspace-menu" aria-controls="clinical-navigation" aria-expanded="${!!S.navOpen}">Menu</button><div><strong>Clinical review workspace</strong><p class="muted" style="margin:4px 0">${esc(S.data.patient.name)} · synthetic data only</p></div>${renderWorkspacePicker()}<div class="actions"><button id="refresh">Refresh saved records</button><a class="button" href="/mobile/">Mobile app</a></div></header><main id="clinical-content" tabindex="-1">${content}</main></div>`;
  bind();
}
function bind() {
  document.querySelectorAll(".table-scroll").forEach((region) => {
    region.tabIndex = 0;
    region.setAttribute("role", "region");
    region.setAttribute("aria-label", "Scrollable evidence table");
  });
  bindWorkspacePicker();
  bindResearchSessions();
  bindCareMessages();
  bindWeeklyReports();
  bindClinicalRoutines();
  bindClinicalSurfaces();
  bindSourcePage();
  if ($("#workspace-menu"))
    $("#workspace-menu").onclick = () => {
      S.navOpen = !S.navOpen;
      render();
      if (S.navOpen) $(".sidebar button.active")?.focus();
    };
  document.onkeydown = (event) => {
    if (event.key === "Escape" && S.navOpen) {
      S.navOpen = false;
      render();
      $("#workspace-menu")?.focus();
    }
  };
  bindEvidenceDraft();
  if (S.sourceBusy || S.draftBusy || S.pdfBusy)
    document
      .querySelectorAll("form input,form select,form textarea,form button")
      .forEach((el) => (el.disabled = true));
  document
    .querySelectorAll(
      "form:not(#care-compose):not(#care-voice-form):not(#care-search):not(#review-filters)",
    )
    .forEach((f) => f.addEventListener("input", () => (S.dirty = true)));
  document.querySelectorAll("[data-tab]").forEach(
    (b) =>
      (b.onclick = () => {
        if (S.dirty && !confirm("Discard unsaved edits?")) return;
        S.dirty = false;
        stopCareCapture();
        S.tab = b.dataset.tab;
        S.navOpen = false;
        if (["sources", "report", "messages"].includes(S.tab)) guard(refresh);
        else render();
      }),
  );
  document.querySelectorAll("[data-case]").forEach(
    (b) =>
      (b.onclick = () => {
        S.caseId = b.dataset.case;
        S.tab = "case";
        render();
      }),
  );
  $("#refresh").onclick = () => {
    if (S.dirty && !confirm("Discard unsaved edits and reload saved records?")) return;
    S.dirty = false;
    guard(refresh);
  };
  $("#dark").onclick = () => document.body.classList.toggle("dark-mode");
  $("#logout").onclick = () =>
    guard(async () => {
      if (
        hasCareDrafts() &&
        !confirm(
          "Discard unsent message drafts? A request with an unconfirmed response may already be saved in the conversation.",
        )
      )
        return;
      await api("/logout", "POST");
      clearPatientContext();
      S.workspaces = [];
      S.user = null;
      S.reportNotes = {};
      S.weekly = null;
      S.reportHistory = [];
      S.reportId = null;
      S.reportEpoch = (S.reportEpoch || 0) + 1;
      S.data = null;
      login();
    });
  if ($("#plan"))
    $("#plan").onsubmit = (e) => {
      e.preventDefault();
      const body = Object.fromEntries(new FormData(e.target));
      body.source_ids = body.source_id ? [body.source_id] : [];
      delete body.source_id;
      guard(async () => {
        await api(`/patients/${S.pid}/plans`, "POST", body);
        S.dirty = false;
        await refresh();
        note("Draft saved. It is not active until reviewed and approved.");
      });
    };
  document.querySelectorAll("[data-approve]").forEach(
    (b) =>
      (b.onclick = () => {
        const p = rows("plan").find((p) => p.id === b.dataset.approve);
        if (
          confirm(
            `Approve revision ${p.version} of “${p.payload.title}”? This supersedes the previous plan. External dispatch is not connected.`,
          )
        )
          guard(async () => {
            await api(`/patients/${S.pid}/plans/${p.id}/approve`, "POST", {
              command_id: crypto.randomUUID(),
              expected_version: p.version,
            });
            await refresh();
            note(
              "Approved revision saved. Mobile can refresh the current plan. No EHR dispatch occurred.",
            );
          });
      }),
  );
  if ($("#review"))
    $("#review").onsubmit = (e) => {
      e.preventDefault();
      const r = rows("case").find((c) => c.id === S.caseId),
        body = Object.fromEntries(new FormData(e.target));
      guard(async () => {
        await api(`/patients/${S.pid}/cases/${r.id}/review`, "POST", {
          ...body,
          command_id: crypto.randomUUID(),
          expected_version: r.version,
        });
        S.dirty = false;
        await refresh();
        note("Decision recorded with your authenticated identity.");
      });
    };
  if ($("#catalog"))
    $("#catalog").onclick = () =>
      guard(async () => {
        $("#catalogResult").textContent = JSON.stringify(await api("/providers/catalog"), null, 2);
      });
  if ($("#loadAudit"))
    $("#loadAudit").onclick = () =>
      guard(async () => {
        const events = await api(`/patients/${S.pid}/audit`);
        $("#auditRows").innerHTML = events
          .map(
            (a) =>
              `<div class="stage"><strong>${esc(a.action)}</strong><span>${esc(a.actor)} · ${esc(new Date(a.created_at).toLocaleString())}</span></div>`,
          )
          .join("");
      });
}
async function start() {
  clearPatientContext();
  S.accountTextLarge = false;
  S.workspaceChanging = false;
  if (S.user.role !== "clinician") {
    location.href = "/mobile/";
    return;
  }
  S.workspaces = await api("/patients");
  if (S.workspaces.length === 1) await activateWorkspace(S.workspaces[0].id, true);
  else workspaceState();
}

(async () => {
  try {
    S.user = await api("/session");
    S.csrf = S.user.csrf;
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
    S.dirty ||
    S.pdfBusy ||
    S.sourceBusy ||
    S.draftBusy ||
    S.reportBusy ||
    S.care?.busy ||
    careVoiceBusy() ||
    careAudioPlaying() ||
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
      S.data = null;
      resetCareMessages();
      S.user = null;
      S.reportNotes = {};
      S.weekly = null;
      S.reportHistory = [];
      S.reportId = null;
      S.reportEpoch = (S.reportEpoch || 0) + 1;
      login();
      note("Access expired or changed. Sign in again.");
    }
  } finally {
    syncing = false;
  }
}, 5000);
