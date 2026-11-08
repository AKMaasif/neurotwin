// Operational views use only records in the currently authorized patient workspace.
const reviewStateLabels = {
  awaiting_review: "Awaiting review",
  information_requested: "Information requested",
  urgent_handoff_required: "Urgent handoff required",
  reviewed: "Reviewed",
  rejected: "Rejected",
};
function clinicalTabAllowed(tab) {
  const scope = {
    queue: "review",
    patient: "review",
    sources: "review",
    routines: "review",
    support: "help",
    messages: "messages",
    providers: "review",
    audit: "audit",
    report: "review",
    case: "review",
  }[tab];
  return !scope || S.data.scopes.includes(scope);
}
function clinicalCaseTable(items = rows("case"), filtered = false) {
  return `<div class="table-scroll clinical-case-table"><table><thead><tr><th scope="col">Reported concern</th><th scope="col">Review state</th><th scope="col">Reported by / recorded</th><th scope="col">Next action</th></tr></thead><tbody>${items.map((item) => `<tr class="${item.payload.urgent_reported ? "case-reported-urgent" : ""}"><td><strong>${esc(item.payload.concern)}</strong>${item.payload.urgent_reported ? '<small class="clinical-urgent-caption">Sudden change reported. Human assistance is required; no emergency dispatch is connected.</small>' : ""}</td><td><span class="review-state state-${esc(item.status)}">${esc(reviewStateLabels[item.status] || item.status.replaceAll("_", " "))}</span></td><td>${esc(item.payload.reported_by)}<small>${esc(new Date(item.created_at).toLocaleString())}</small></td><td><button data-case="${esc(item.id)}">Review evidence</button></td></tr>`).join("") || `<tr><td colspan="4"><div class="clinical-empty"><strong>${filtered ? "No matching concerns" : "No concerns submitted"}</strong><p>${filtered ? "Change or clear your filters to see other recorded concerns." : "A participant can report a concern from Support. No reported concerns does not establish clinical stability."}</p></div></td></tr>`}</tbody></table></div>`;
}
function renderClinicalOverview() {
  const canReview = S.data.scopes.includes("review");
  const cases = rows("case"),
    pending = cases.filter((item) => item.status === "awaiting_review");
  const urgent = cases.filter((item) => item.status === "urgent_handoff_required");
  const held = rows("plan").filter((plan) => plan.payload.source_review_required);
  const tasks = rows("task").filter(
    (task) =>
      task.status !== "superseded" &&
      !task.payload.is_routine_template &&
      rows("plan").some((plan) => plan.id === task.payload.plan_id && plan.status === "approved"),
  );
  const recent = [...cases].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 5);
  return `<div class="clinical-overview"><div class="clinical-page-heading"><p class="clinical-kicker">EVIDENCE BEFORE ACTION</p><h1>Clinical overview</h1><p>Review the current assigned patient, source holds and reported concerns.</p></div><section class="clinical-patient-spotlight"><div><span class="clinical-kicker">CURRENT ASSIGNED WORKSPACE</span><h2>${esc(S.data.patient.name)}</h2><p>${esc(S.data.patient.region)} · ${esc(S.data.patient.age)} years · Synthetic record</p>${canReview ? '<button class="primary" data-tab="patient">Open patient workspace</button>' : '<p class="muted">Activity-summary access only.</p>'}</div><div class="clinical-workload"><div><strong>${canReview ? pending.length : "—"}</strong><span>${canReview ? "Awaiting review" : "Review access not granted"}</span></div><div><strong>${held.length}</strong><span>Plans with source holds</span></div><div><strong>${tasks.length}</strong><span>Current plan tasks</span></div></div></section>${urgent.length ? `<aside class="clinical-urgent-strip"><strong>${urgent.length} reported ${urgent.length === 1 ? "concern requires" : "concerns require"} urgent human handoff</strong><p>The report is a safety flag, not an automated diagnosis or confirmed emergency response.</p><button data-queue-state="urgent_handoff_required">View handoff records</button></aside>` : ""}<div class="clinical-evidence-grid"><section class="card clinical-activity-evidence"><div class="clinical-section-heading"><h2>Recorded activity</h2><span class="clinical-evidence-label">CURRENT RECORDS</span></div><p class="clinical-evidence-narrative">${esc(S.report?.narrative || "Activity evidence is unavailable.")}</p><p class="muted">${esc(S.report?.evidence || "No evidence summary loaded.")}</p>${canReview ? '<button data-tab="report">Open activity report</button>' : ""}</section><section class="card clinical-source-status"><span class="clinical-kicker">EVIDENCE READINESS</span><h2>${held.length ? "Source corrections need review" : "Review the original evidence"}</h2><p>${held.length ? `${held.length} ${held.length === 1 ? "plan is" : "plans are"} flagged for source review. A prior approval does not clear a changed source.` : "Verify source facts before creating or approving a source-linked plan."}</p>${canReview ? '<button data-tab="sources">Open source verification</button>' : '<p class="muted">Clinical source access is not granted for this workspace.</p>'}<details><summary>Research model status</summary><p>${rows("model").length ? "Research results are available in Patient workspace." : "Insufficient history. No stability or disease score is available."}</p><p>Clinical model not validated.</p></details></section></div><section class="card clinical-review-preview"><div class="clinical-section-heading"><div><span class="clinical-kicker">REPORTED CONCERNS</span><h2>Review pipeline</h2></div>${canReview ? '<button data-tab="queue">Open review queue</button>' : ""}</div><p class="muted">Up to five most recently recorded concerns for this patient. Open the queue for all states.</p>${canReview ? clinicalCaseTable(recent) : "<p>Reported concern details are not included in your current access.</p>"}</section><footer class="clinical-data-note">Updated ${esc(new Date(S.data.as_of).toLocaleString())}. EHR and external dispatch are not connected. This is one authorized patient workspace, not a population-wide caseload.</footer></div>`;
}
function renderClinicalQueue() {
  const filter = S.queueFilter || "",
    query = (S.queueQuery || "").trim().toLowerCase();
  const cases = rows("case");
  const shown = cases.filter(
    (item) =>
      (!filter || item.status === filter) &&
      (!query ||
        [item.payload.concern, item.payload.reported_by].some((value) =>
          String(value || "")
            .toLowerCase()
            .includes(query),
        )),
  );
  const priority = {
    urgent_handoff_required: 0,
    awaiting_review: 1,
    information_requested: 2,
    reviewed: 3,
    rejected: 4,
  };
  shown.sort(
    (a, b) =>
      (priority[a.status] ?? 5) - (priority[b.status] ?? 5) ||
      b.created_at.localeCompare(a.created_at),
  );
  const options = [["", "All concerns"], ...Object.entries(reviewStateLabels)];
  return `<div class="clinical-queue"><div class="clinical-page-heading"><p class="clinical-kicker">HUMAN REVIEW</p><h1>Assigned review queue</h1><p>Reported concerns remain visible independently of numerical results.</p></div><section class="clinical-queue-context"><strong>${esc(S.data.patient.name)}</strong><span>${shown.length} shown of ${cases.length} recorded concerns</span><small>Current authorized patient only</small></section><section class="card clinical-queue-surface"><form id="review-filters"><label>Search concerns<input name="query" value="${esc(S.queueQuery || "")}" maxlength="200" placeholder="Concern or reporter"></label><label>Review state<select name="state">${options.map(([value, label]) => `<option value="${value}" ${filter === value ? "selected" : ""}>${label}</option>`).join("")}</select></label><button class="primary">Apply filters</button><button type="button" id="clear-review-filters">Clear</button></form><p class="clinical-filter-result" role="status">${shown.length} ${shown.length === 1 ? "concern" : "concerns"} shown. Filtering changes only this view.</p>${clinicalCaseTable(shown, !!filter || !!query)}</section><p class="clinical-data-note">Urgent handoff records retain their human-assistance boundary. Selecting Review evidence does not approve a decision or dispatch a referral.</p></div>`;
}
function bindClinicalSurfaces() {
  if (document.querySelector("#review-filters"))
    document.querySelector("#review-filters").onsubmit = (event) => {
      event.preventDefault();
      const form = new FormData(event.target);
      S.queueQuery = form.get("query");
      S.queueFilter = form.get("state");
      render();
    };
  if (document.querySelector("#clear-review-filters"))
    document.querySelector("#clear-review-filters").onclick = () => {
      S.queueQuery = "";
      S.queueFilter = "";
      render();
    };
  document.querySelectorAll("[data-queue-state]").forEach(
    (button) =>
      (button.onclick = () => {
        S.queueFilter = button.dataset.queueState;
        S.queueQuery = "";
        S.tab = "queue";
        render();
        window.scrollTo(0, 0);
      }),
  );
}

function renderClinicalPatient() {
  const plans = [...rows("plan")].sort((a, b) => b.created_at.localeCompare(a.created_at));
  const active = plans.filter((plan) => plan.status === "approved");
  const tasks = rows("task").filter(
    (task) =>
      task.status !== "superseded" &&
      !task.payload.is_routine_template &&
      active.some((plan) => plan.id === task.payload.plan_id),
  );
  return `<div class="clinical-patient"><div class="clinical-page-heading"><p class="clinical-kicker">PATIENT WORKSPACE</p><h1>${esc(S.data.patient.name)}</h1><p>${esc(S.data.patient.region)} · ${S.data.patient.age} years · Synthetic record</p></div><section class="card clinical-plan-summary"><h2>Current support</h2><p>${active.length} approved ${active.length === 1 ? "plan" : "plans"} · ${tasks.length} current ${tasks.length === 1 ? "task" : "tasks"}. Patient responses are self-reported, not proof of treatment adherence.</p><div class="clinical-task-list">${tasks.map((task) => `<article><strong>${esc(task.payload.title)}</strong><span class="review-state">${esc(task.status.replaceAll("_", " "))}</span><small>${esc(task.payload.response?.evidence || task.payload.evidence_type || "No response evidence recorded")}</small></article>`).join("") || "<p>No current tasks are recorded.</p>"}</div></section><div class="clinical-patient-grid"><section class="card clinical-plan-history"><span class="clinical-kicker">VERSIONED RECORDS</span><h2>Current plan and revisions</h2><p class="muted">Approval replaces the current support plan. Drafts remain hidden from patient and family views.</p>${
    plans
      .map(
        (plan) =>
          `<article class="clinical-plan-entry"><div class="clinical-section-heading"><h3>${esc(plan.payload.title)}</h3><span class="review-state">${esc(plan.status)} · v${plan.version}</span></div><p class="clinical-plan-instructions">${esc(plan.payload.instructions)}</p><dl class="clinical-metadata"><dt>Recorded</dt><dd>${esc(new Date(plan.created_at).toLocaleString())}</dd><dt>Approval</dt><dd>${esc(plan.payload.signed_by || "Awaiting approval")}${plan.payload.signed_at ? " · " + esc(new Date(plan.payload.signed_at).toLocaleString()) : ""}</dd><dt>Linked sources</dt><dd>${
            Object.entries(plan.payload.source_versions || {})
              .map(([id, version]) => {
                const source = (S.documents || []).find((d) => d.id === id);
                return esc(source?.payload.title || id) + " · v" + esc(version);
              })
              .join("<br>") || "No linked source — support task only"
          }</dd></dl>${plan.payload.source_review_required ? '<p class="source-warning" role="status">A linked source changed. Clinical review is required.</p>' : ""}${plan.status === "draft" ? `<button class="primary" data-approve="${esc(plan.id)}">Review and approve this revision</button>` : ""}<details><summary>Record provenance</summary><p class="muted">Record ${esc(plan.id)} · ${esc(plan.payload.signature_type || "No authenticated approval recorded")}</p><p class="muted">${esc(plan.payload.content_hash || "No approval content hash recorded")}</p></details></article>`,
      )
      .join("") || "<p>No plans recorded.</p>"
  }</section><section class="card clinical-plan-create"><span class="clinical-kicker">HUMAN-AUTHORED SUPPORT</span><h2>Propose a support plan</h2><p class="muted">Only non-prescribing support templates are enabled in this build. Saving creates a draft; it does not change the active plan.</p><form id="plan"><label>Template<select name="template"><option value="appointment_preparation">Appointment preparation</option><option value="social_contact">Social contact</option></select></label><label>Title<input name="title" maxlength="150" required></label><label>Verified source<select name="source_id"><option value="">No linked source — support task only</option>${(
    S.documents || []
  )
    .filter(
      (d) => d.status === "reviewed" && d.payload.candidates.some((f) => f.status === "verified"),
    )
    .map((d) => `<option value="${d.id}">${esc(d.payload.title)} · v${d.version}</option>`)
    .join(
      "",
    )}</select></label><label>Instruction<textarea name="instructions" maxlength="1500" required></textarea></label><button>Save draft</button></form></section></div>${renderAssessmentPanel()}${renderResearchPanel()}${renderIotSimulation()}<section class="card"><h2>Research model results</h2><p class="muted">Illustrative research output. Not a validated diagnosis, clinical score or referral decision.</p>${
    rows("model")
      .map(
        (model) =>
          `<details><summary>Research artifact · ${esc(new Date(model.created_at).toLocaleString())}</summary><pre class="source">${esc(JSON.stringify(model.payload, null, 2))}</pre></details>`,
      )
      .join("") || "<p>No model result. Missing data remains unavailable.</p>"
  }</section></div>`;
}

function renderClinicalCase() {
  const item = rows("case").find((record) => record.id === S.caseId);
  if (!item)
    return '<h1>Review evidence</h1><section class="card"><h2>Case unavailable</h2><p>This record is not in the current authorized workspace.</p><button data-tab="queue">Return to work queue</button></section>';
  const p = item.payload,
    urgent = !!p.urgent_reported || item.status === "urgent_handoff_required";
  const editable = !urgent && ["awaiting_review", "information_requested"].includes(item.status);
  return `<div class="clinical-case"><div class="clinical-page-heading"><p class="clinical-kicker">ATTRIBUTED EVIDENCE · HUMAN DECISION</p><h1>Review evidence</h1><p>${esc(S.data.patient.name)} · Record revision ${item.version}</p><button data-tab="queue">Return to work queue</button></div>${urgent ? '<aside class="clinical-urgent-strip"><strong>Urgent human handoff required</strong><p>This app has not contacted emergency services. Use the locally approved human assistance route; routine review cannot clear this flag.</p></aside>' : ""}<div class="clinical-evidence-grid"><section class="card"><span class="clinical-kicker">ORIGINAL REPORTED CONCERN</span><h2>Attributed source</h2><blockquote class="clinical-concern">${esc(p.concern)}</blockquote><dl class="clinical-metadata"><dt>Reporter account</dt><dd>${esc(p.reported_by || "Not recorded")}</dd><dt>Recorded</dt><dd>${esc(new Date(item.created_at).toLocaleString())}</dd><dt>Workflow state</dt><dd><span class="review-state state-${esc(item.status)}">${esc(reviewStateLabels[item.status] || item.status)}</span></dd><dt>Record ID</dt><dd>${esc(item.id)}</dd></dl><h2>Intake workflow stages</h2><p class="muted">These stages were recorded at intake. The current review state and clinician decision are shown separately. They are not model accuracy scores; missing producer attribution remains unavailable.</p><ol class="clinical-stage-list">${(p.stages || []).map((stage) => `<li><strong>${esc(String(stage.stage).replaceAll("_", " "))}</strong><span>${esc(String(stage.status).replaceAll("_", " "))}</span><small>${esc(stage.producer || "Producer not recorded")}</small></li>`).join("") || "<li>No stage evidence recorded.</li>"}</ol></section><section class="card clinical-decision"><span class="clinical-kicker">AUTHENTICATED CLINICIAN</span><h2>Human decision</h2><p>Current revision: ${item.version}. No external referral is dispatched by this action.</p>${p.reviewed_at ? `<dl class="clinical-metadata"><dt>Last reviewer</dt><dd>${esc(p.reviewer)}</dd><dt>Decision recorded</dt><dd>${esc(new Date(p.reviewed_at).toLocaleString())}</dd><dt>Rationale</dt><dd>${esc(p.rationale)}</dd></dl>` : ""}${editable ? `<form id="review"><label>Decision<select name="decision"><option value="approve">Record review completed</option><option value="request_information">Request information</option><option value="reject">Reject proposal</option></select></label><label>Rationale<textarea name="rationale" required minlength="3" maxlength="2000" placeholder="Record the evidence and reasoning behind your decision."></textarea></label><p class="muted">This records a workflow decision. It does not send a message, create a plan, or establish a diagnosis.</p><button class="primary">Confirm decision</button></form>` : `<p>${esc(urgent ? "Urgent handoff requires a human assistance path; this app has not contacted emergency services." : "This record is closed to further routine decisions.")}</p>`}</section></div></div>`;
}
