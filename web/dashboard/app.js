const S = { user: null, csrf: "", data: null, pid: null, tab: "overview", report: null };
const $ = (s) => document.querySelector(s);
const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
async function api(path, method = "GET", body) {
  const r = await fetch("/api" + path, {
    method,
    headers: { ...(body ? { "Content-Type": "application/json" } : {}), "X-CSRF-Token": S.csrf },
    body: body ? JSON.stringify(body) : undefined,
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) {
    const error = new Error(typeof d.detail === "string" ? d.detail : "Request failed");
    error.status = r.status;
    throw error;
  }
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
  S.data = await api(`/patients/${S.pid}/workspace`);
  S.report = await api(`/patients/${S.pid}/report`);
  S.routineData = await api(`/patients/${S.pid}/routines`);
  S.documents = await api(`/patients/${S.pid}/documents`);
  if (S.tab === "sources") {
    if (!S.documents.some((d) => d.id === S.documentId)) S.documentId = S.documents[0]?.id;
    S.documentDetails = S.documentId
      ? await api(`/patients/${S.pid}/documents/${S.documentId}/details`)
      : null;
  }
  if (S.tab === "report") await loadWeeklyReports();
  if (S.tab === "messages") await loadCareMessages();
  render();
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
function caseTable() {
  return `<div class="table-scroll"><table><thead><tr><th>Concern</th><th>State</th><th>Reported by</th><th>Next action</th></tr></thead><tbody>${
    rows("case")
      .map(
        (r) =>
          `<tr><td>${esc(r.payload.concern)}</td><td><span class="badge hold">${esc(r.status)}</span></td><td>${esc(r.payload.reported_by)}</td><td><button data-case="${r.id}">Review evidence</button></td></tr>`,
      )
      .join("") ||
    '<tr><td colspan="4">No concerns submitted. A participant can report one from Support.</td></tr>'
  }</tbody></table></div>`;
}
function render() {
  let content = "";
  const cases = rows("case"),
    pending = cases.filter((r) => r.status === "awaiting_review");
  if (S.tab === "overview")
    content = `<h1>Clinical caseload & active concerns</h1><p>Assigned patient evidence and follow-up. Synthetic development environment.</p><section class="card"><div class="eyebrow">CURRENT ASSIGNED WORKSPACE</div><div class="stat">${esc(S.data.patient.name)}</div><div class="strip"><span style="width:100%"></span></div><div class="actions"><span class="badge">${pending.length} awaiting review</span><span class="badge">${rows("task").filter((t) => t.status !== "superseded" && !t.payload.is_routine_template && rows("plan").some((p) => p.id === t.payload.plan_id && p.status === "approved")).length} current tasks</span><span class="badge hold">Clinical model not validated</span></div><p class="muted">Updated ${esc(new Date(S.data.as_of).toLocaleString())}. EHR and external dispatch are not connected.</p></section><div class="grid"><section class="card"><h2>Current activity evidence</h2><p>${esc(S.report.narrative)}</p><p class="muted">${esc(S.report.evidence)}</p></section><section class="card"><h2>Longitudinal measurements</h2><p>${rows("model").length ? "Research results are available in Patient workspace." : "Insufficient history. No stability or disease score is available."}</p><button data-tab="patient">Open patient workspace</button></section></div><section class="card"><h2>Review pipeline</h2>${caseTable()}</section>`;
  if (S.tab === "queue")
    content = `<h1>Assigned review queue</h1><p>Reported concerns remain visible independently of numerical results.</p><section class="card">${caseTable()}</section>`;
  if (S.tab === "patient")
    content = `<h1>${esc(S.data.patient.name)}</h1><p>${esc(S.data.patient.region)} · ${S.data.patient.age} years · Synthetic record</p><section class="card"><h2>Current plan and revisions</h2>${rows(
      "plan",
    )
      .map(
        (p) =>
          `<section class="source"><span class="badge">${esc(p.status)} · v${p.version}</span><h3>${esc(p.payload.title)}</h3><p>${esc(p.payload.instructions)}</p><p class="muted">${esc(p.payload.signed_by || "Awaiting approval")}</p>${p.payload.source_review_required ? '<p class="source-warning">A linked source changed. Clinical review is required.</p>' : ""}${p.status === "draft" ? `<button class="primary" data-approve="${p.id}">Review and approve this revision</button>` : ""}</section>`,
      )
      .join(
        "",
      )}</section><section class="card"><h2>Propose a support plan</h2><p class="muted">Only non-prescribing support templates are enabled in this build.</p><form id="plan"><label>Template<select name="template"><option value="appointment_preparation">Appointment preparation</option><option value="social_contact">Social contact</option></select></label><label>Title<input name="title" maxlength="150" required></label><label>Verified source<select name="source_id"><option value="">No linked source — support task only</option>${(
      S.documents || []
    )
      .filter(
        (d) => d.status === "reviewed" && d.payload.candidates.some((f) => f.status === "verified"),
      )
      .map((d) => `<option value="${d.id}">${esc(d.payload.title)} · v${d.version}</option>`)
      .join(
        "",
      )}</select></label><label>Instruction<textarea name="instructions" maxlength="1500" required></textarea></label><button>Save draft</button></form></section><section class="card"><h2>Research model results</h2>${
      rows("model")
        .map((m) => `<pre class="source">${esc(JSON.stringify(m.payload, null, 2))}</pre>`)
        .join("") || "<p>No model result. Missing data remains unavailable.</p>"
    }</section>`;
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
  if (S.tab === "case") {
    const r = cases.find((c) => c.id === S.caseId);
    content = r
      ? `<h1>Review evidence</h1><div class="grid"><section class="card"><h2>Attributed source</h2><p class="source">${esc(r.payload.concern)}</p><p>Reported by ${esc(r.payload.reported_by)}</p><span class="badge hold">${esc(r.status)}</span><h2 style="margin-top:20px">Workflow stages</h2>${r.payload.stages.map((s) => `<div class="stage"><strong>${esc(s.stage.replaceAll("_", " "))}</strong><span>${esc(s.status.replaceAll("_", " "))}</span></div>`).join("")}</section><section class="card"><h2>Human decision</h2><p>Current revision: ${r.version}. No external referral is dispatched by this action.</p>${["awaiting_review", "information_requested"].includes(r.status) ? `<form id="review"><label>Decision<select name="decision"><option value="approve">Record review completed</option><option value="request_information">Request information</option><option value="reject">Reject proposal</option></select></label><label>Rationale<textarea name="rationale" required minlength="3"></textarea></label><button class="primary">Confirm decision</button></form>` : `<p>${esc(r.payload.rationale || "Urgent handoff requires a human assistance path; this app has not contacted emergency services.")}</p>`}</section></div>`
      : "<p>Case unavailable.</p>";
  }
  if (S.tab === "case" && cases.some((c) => c.id === S.caseId && !c.payload.urgent_reported))
    content += renderEvidenceDrafts(S.caseId);
  $("#app").innerHTML =
    `<aside class="sidebar"><div class="brand">NeuroTwin<div class="eyebrow">CLINICAL MONITORING</div></div><span class="eyebrow">MONITOR</span>${[
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
      .map(
        ([k, n]) => `<button data-tab="${k}" class="${S.tab === k ? "active" : ""}">${n}</button>`,
      )
      .join(
        "",
      )}<div class="bottom"><p><strong>${esc(S.user.name)}</strong><br>Assigned clinician</p><button id="dark">Dark mode</button><button id="logout">Sign out</button></div></aside><div class="main"><header class="topbar"><div><strong>Clinical review workspace</strong><p class="muted" style="margin:4px 0">${esc(S.data.patient.name)} · synthetic data only</p></div><div class="actions"><button id="refresh">Refresh saved records</button><a class="button" href="/mobile/">Mobile app</a></div></header><main>${content}</main></div>`;
  bind();
}
function bind() {
  bindCareMessages();
  bindWeeklyReports();
  bindClinicalRoutines();
  bindSourcePage();
  bindEvidenceDraft();
  if (S.sourceBusy || S.draftBusy || S.pdfBusy)
    document
      .querySelectorAll("form input,form select,form textarea,form button")
      .forEach((el) => (el.disabled = true));
  document
    .querySelectorAll("form:not(#care-compose)")
    .forEach((f) => f.addEventListener("input", () => (S.dirty = true)));
  document.querySelectorAll("[data-tab]").forEach(
    (b) =>
      (b.onclick = () => {
        if (S.dirty && !confirm("Discard unsaved edits?")) return;
        S.dirty = false;
        S.tab = b.dataset.tab;
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
      resetCareMessages();
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
  S.tab = "overview";
  resetCareMessages();
  S.reportNotes = {};
  S.weekly = null;
  S.reportHistory = [];
  S.reportId = null;
  S.reportEnd = null;
  S.reportZone = "Asia/Dubai";
  S.dirty = false;
  S.reportEpoch = (S.reportEpoch || 0) + 1;
  if (S.user.role !== "clinician") {
    location.href = "/mobile/";
    return;
  }
  const ps = await api("/patients");
  S.pid = ps[0]?.id;
  if (!S.pid) throw new Error("No assigned patient");
  await refresh();
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
    syncing ||
    S.dirty ||
    S.pdfBusy ||
    S.sourceBusy ||
    S.draftBusy ||
    S.reportBusy ||
    S.care?.busy ||
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
